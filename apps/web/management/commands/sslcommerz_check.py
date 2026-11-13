"""SSLCommerz সংযোগ পরীক্ষা — স্যান্ডবক্সে পাস হলে তারপর LIVE-এ যান।

    python manage.py sslcommerz_check                 # কোনো টাকা কাটে না; শুধু সেশন তৈরি হয়
    python manage.py sslcommerz_check --amount 10     # নির্দিষ্ট অ্যামাউন্ট দিয়ে

যা যাচাই হয়: ক্রেডেনশিয়াল সেট আছে কি না, গেটওয়ের সাথে যোগাযোগ, GatewayPageURL পাওয়া যায় কি না।
লাইভে যাওয়ার আগে: SSLCOMMERZ_SANDBOX=True দিয়ে `manage.py sslcommerz_check` পাস করুন,
তারপর SSLCOMMERZ_SANDBOX=False করে আবার চালান (তখন আসল স্টোর ক্রেডেনশিয়াল লাগবে)।
"""
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.payments.gateways import GatewayError, SSLCommerzGateway


class Command(BaseCommand):
    help = "SSLCommerz স্যান্ডবক্স/লাইভ সংযোগ ও ক্রেডেনশিয়াল পরীক্ষা (কোনো টাকা কাটে না)"

    def add_arguments(self, parser):
        parser.add_argument("--amount", default="10", help="টেস্ট অ্যামাউন্ট (ডিফল্ট ১০ টাকা)")

    def handle(self, *args, **options):
        if not (settings.SSLCOMMERZ_STORE_ID and settings.SSLCOMMERZ_STORE_PASSWORD):
            raise CommandError("SSLCOMMERZ_STORE_ID / SSLCOMMERZ_STORE_PASSWORD .env-এ সেট নেই।")
        try:
            amount = Decimal(str(options["amount"]))
        except Exception:
            raise CommandError("অ্যামাউন্ট সংখ্যা হতে হবে।")
        if amount <= 0:
            raise CommandError("অ্যামাউন্ট শূন্যের বেশি হতে হবে।")

        mode = "SANDBOX" if settings.SSLCOMMERZ_SANDBOX else "LIVE"
        self.stdout.write(f"[{mode}] SSLCommerz যাচাই শুরু — store: {settings.SSLCOMMERZ_STORE_ID[:6]}…")

        # নকল পেমেন্ট অবজেক্ট: DB-তে কিছু লেখা হয় না
        from types import SimpleNamespace

        payment = SimpleNamespace(
            amount=amount, tran_id="OMCHECK" + str(int(amount * 100)), plan=SimpleNamespace(name="Check"),
            restaurant=SimpleNamespace(address="Dhaka"),
        )
        user = SimpleNamespace(get_full_name=lambda: "OrderMama Check", username="check",
                               email="check@example.com", phone="01700000000")
        gateway = SSLCommerzGateway()
        self.stdout.write(f"গেটওয়ে বেস URL: {gateway.base}")
        try:
            url = gateway.initiate(payment, user)
        except GatewayError as exc:
            raise CommandError(f"ব্যর্থ: {exc}")
        except Exception as exc:  # নেটওয়ার্ক/JSON ত্রুটি
            raise CommandError(f"গেটওয়ের সাথে যোগাযোগ ব্যর্থ ({exc.__class__.__name__}: {exc})")

        if not str(url).startswith("http"):
            raise CommandError(f"অপ্রত্যাশিত রেসপন্স: {url!r}")
        self.stdout.write(self.style.SUCCESS(f"সফল — সেশন তৈরি হয়েছে: {url[:80]}…"))
        if not settings.SSLCOMMERZ_SANDBOX:
            self.stdout.write(self.style.WARNING(
                "LIVE মোডে আছেন — একটি ছোট আসল পেমেন্ট করে success/fail ফ্লো যাচাই করুন।"))
