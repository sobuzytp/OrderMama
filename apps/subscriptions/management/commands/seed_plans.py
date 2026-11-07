from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.subscriptions.models import Plan


class Command(BaseCommand):
    help = "বেসিক ও প্রিমিয়াম প্ল্যান তৈরি/আপডেট করে।"

    def handle(self, *args, **options):
        Plan.objects.update_or_create(
            code="basic",
            defaults=dict(name="বেসিক", price=Decimal("499"), duration_days=30,
                          live_orders=False, qr_generator=False, branding=False),
        )
        Plan.objects.update_or_create(
            code="premium",
            defaults=dict(name="প্রিমিয়াম", price=Decimal("1499"), duration_days=30,
                          live_orders=True, qr_generator=True, branding=True),
        )
        self.stdout.write(self.style.SUCCESS("প্ল্যান প্রস্তুত।"))
