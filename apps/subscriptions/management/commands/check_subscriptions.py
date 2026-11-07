"""দিনে একবার চালান (cron): মেয়াদ শেষের ৩ দিন আগে সতর্কতা চিহ্নিত করে এবং সুপার অ্যাডমিনের জন্য তালিকা দেখায়।

   0 9 * * *  cd /path/to/ordermama && python manage.py check_subscriptions
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.subscriptions.models import Subscription


class Command(BaseCommand):
    help = "মেয়াদ-সতর্কতা যাচাই"

    def handle(self, *args, **options):
        now = timezone.now()
        soon = now + timedelta(days=settings.SUBSCRIPTION_WARNING_DAYS)
        warn = Subscription.objects.filter(end_date__gte=now, end_date__lte=soon, warning_sent_at__isnull=True)
        for sub in warn.select_related("restaurant", "plan"):
            sub.warning_sent_at = now
            sub.save(update_fields=["warning_sent_at"])
            self.stdout.write(f"সতর্কতা: {sub.restaurant.name} - মেয়াদ শেষ {sub.end_date:%Y-%m-%d}")
        grace = Subscription.objects.filter(end_date__lt=now)
        for sub in grace.select_related("restaurant"):
            self.stdout.write(f"{sub.restaurant.name}: {sub.state}")
