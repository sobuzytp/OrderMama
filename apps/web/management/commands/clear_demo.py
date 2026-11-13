"""ডেমো ডেটা পরিষ্কার (প্রোডাকশনে যাওয়ার আগে): seed_demo যা বানায় তা মুছে দেয়।

    python manage.py clear_demo --dry-run     # কী মুছবে দেখুন
    python manage.py clear_demo               # আসল মোছা (নিশ্চিতকরণ লাগে)
    python manage.py clear_demo --yes         # নিশ্চিতকরণ ছাড়া (স্ক্রিপ্টে)
    python manage.py clear_demo --with-admin  # `admin` সুপার অ্যাডমিনও মুছুন

সতর্কতা: এটি ডেমো রেস্টুরেন্ট (slug `demo-…`), তাদের স্টাফ/মেনু/অর্ডার ও ডিফল্ট পাসওয়ার্ডের
অ্যাকাউন্টগুলো মুছে/নিষ্ক্রিয় করে। আসল রেস্টুরেন্টের ডেটা স্পর্শ করে না।
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.restaurants.models import Restaurant

DEMO_SLUG_PREFIX = "demo-"
DEMO_PASSWORDS = ("demo12345", "admin12345")


class Command(BaseCommand):
    help = "seed_demo-র বানানো ডেমো রেস্টুরেন্ট, স্টাফ ও ডিফল্ট সুপার অ্যাডমিন সরান"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="কিছু না মুছে শুধু দেখান")
        parser.add_argument("--yes", action="store_true", help="নিশ্চিতকরণ ছাড়া চালান")
        parser.add_argument("--with-admin", action="store_true", help="`admin` সুপার অ্যাডমিনও মুছুন")

    def handle(self, *args, **options):
        User = get_user_model()
        dry = options["dry_run"]
        rests = Restaurant.objects.filter(slug__startswith=DEMO_SLUG_PREFIX)
        rest_rows = list(rests.values_list("slug", "name"))

        demo_users = [u for u in User.objects.all() if u.has_usable_password()
                      and any(u.check_password(p) for p in DEMO_PASSWORDS)]
        if not options["with_admin"]:
            demo_users = [u for u in demo_users if u.username != "admin"]
        else:
            demo_users += list(User.objects.filter(username="admin", is_superuser=True))

        self.stdout.write(f"ডেমো রেস্টুরেন্ট ({len(rest_rows)}): {[s for s, _ in rest_rows] or 'নেই'}")
        self.stdout.write(f"ডিফল্ট পাসওয়ার্ডের অ্যাকাউন্ট ({len(demo_users)}): {[u.username for u in demo_users] or 'নেই'}")

        if not rest_rows and not demo_users:
            self.stdout.write(self.style.SUCCESS("মুছতে কিছু নেই।"))
            return

        if dry:
            self.stdout.write(self.style.WARNING("--dry-run: কিছুই মুছিনি।"))
            return

        if not options["yes"]:
            if not settings.DEBUG:
                raise CommandError("প্রোডাকশনে নিশ্চিতকরণ লাগবে: --yes দিন।")
            answer = input("মুছে ফেলতে চান? লিখুন 'yes': ").strip().lower()
            if answer != "yes":
                raise CommandError("বাতিল করা হলো।")

        for r in rests:
            r.delete()  # CASCADE: স্টাফ, মেনু, টেবিল, অর্ডার, পেমেন্ট, সাবস্ক্রিপশন
        for u in demo_users:
            u.delete()
        self.stdout.write(self.style.SUCCESS(
            f"মোছা হয়েছে — {len(rest_rows)} রেস্টুরেন্ট, {len(demo_users)} অ্যাকাউন্ট।"))
        self.stdout.write("এরপর `manage.py check_production` চালিয়ে নিশ্চিত হোন।")
