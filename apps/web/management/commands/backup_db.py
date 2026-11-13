"""ডেটাবেজ ব্যাকআপ (rotation সহ) — VPS/cPanel-এ cron দিয়ে দিনে একবার।

    python manage.py backup_db                 # BACKUP_DIR-এ গেলে + পুরনো মুছে
    python manage.py backup_db --keep 30       # শেষ ৩০টি রাখুন
    python manage.py backup_db -o /tmp/x.sql.gz

SQLite হলে ফাইল কপি (WAL-safe), PostgreSQL হলে `pg_dump | gzip`। MEDIA আলাদা ব্যাকআপ করুন।
"""
import gzip
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "ডেটাবেজের gzip ব্যাকআপ নেয় এবং পুরনো ফাইল পরিষ্কার করে"

    def add_arguments(self, parser):
        parser.add_argument("--keep", type=int, default=14, help="যতগুলো সাম্প্রতিক ব্যাকআপ রাখবেন (ডিফল্ট ১৪)")
        parser.add_argument("-o", "--output", help="নির্দিষ্ট ফাইল-পাথে রাখুন (rotation হবে না)")

    def handle(self, *args, **options):
        keep = max(1, options["keep"])
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        target = Path(options["output"]) if options["output"] else Path(settings.BACKUP_DIR) / f"db-{stamp}.gz"
        target.parent.mkdir(parents=True, exist_ok=True)

        engine = connection.settings_dict["ENGINE"]
        if "postgresql" in engine:
            self.dump_postgres(target)
        elif "sqlite3" in engine:
            self.dump_sqlite(target)
        else:
            raise CommandError(f"এই ডেটাবেজ ইঞ্জিনের ব্যাকআপ সাপোর্ট করে না: {engine}")

        size_mb = target.stat().st_size / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"ব্যাকআপ তৈরি: {target} ({size_mb:.2f} MB)"))
        if not options["output"]:
            self.rotate(Path(settings.BACKUP_DIR), keep)

    def dump_postgres(self, target):
        db = connection.settings_dict
        env = {"PGPASSWORD": db.get("PASSWORD") or ""}
        cmd = [
            "pg_dump", "--no-owner", "--no-privileges",
            "-h", str(db.get("HOST") or "localhost"), "-p", str(db.get("PORT") or 5432),
            "-U", str(db.get("USER") or "postgres"), str(db["NAME"]),
        ]
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env={**env})
        except FileNotFoundError:
            raise CommandError("pg_dump পাওয়া যাচ্ছে না। PostgreSQL ক্লায়েন্ট ইনস্টল করুন।")
        with gzip.open(target, "wb") as out:
            shutil.copyfileobj(proc.stdout, out)
        err = proc.stderr.read().decode("utf-8", "ignore").strip()
        if proc.wait() != 0:
            target.unlink(missing_ok=True)
            raise CommandError(f"pg_dump ব্যর্থ: {err or 'অজানা ত্রুটি'}")

    def dump_sqlite(self, target):
        path = Path(connection.settings_dict["NAME"])
        if not path.exists():
            raise CommandError(f"SQLite ফাইল পাওয়া যায়নি: {path}")
        import sqlite3
        import tempfile

        # WAL মোডেও নিখুঁত স্ন্যাপশট: sqlite3-এর backup API
        with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as tmp:
            snap = Path(tmp.name)
        try:
            src = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            dst = sqlite3.connect(snap)
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            with open(snap, "rb") as fh, gzip.open(target, "wb") as out:
                shutil.copyfileobj(fh, out)
        finally:
            snap.unlink(missing_ok=True)

    def rotate(self, folder, keep):
        files = sorted(folder.glob("db-*.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[keep:]:
            old.unlink(missing_ok=True)
            self.stdout.write(f"পুরনো ব্যাকআপ মুছে ফেলা হলো: {old.name}")
