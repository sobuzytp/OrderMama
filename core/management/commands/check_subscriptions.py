"""E-mail owners whose subscription is about to expire.

Run daily from a cPanel cron job:
    /path/to/venv/bin/python /path/to/manage.py check_subscriptions
"""
from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import RestaurantMembership, Subscription


class Command(BaseCommand):
    help = "Send expiry alerts for subscriptions ending soon (once per subscription)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=settings.SUBSCRIPTION_ALERT_DAYS)

    def handle(self, *args, **options):
        sent = 0
        pending = Subscription.objects.filter(active=True, expiry_alert_sent_at__isnull=True).select_related("restaurant", "plan")
        for subscription in pending:
            if not subscription.expires_within(options["days"]):
                continue
            latest = subscription.restaurant.current_subscription
            if latest and latest.pk != subscription.pk:
                continue  # already renewed with a later subscription
            owners = RestaurantMembership.objects.filter(
                restaurant=subscription.restaurant, role="owner",
            ).select_related("user")
            recipients = [m.user.email for m in owners if m.user.email]
            if recipients:
                send_mail(
                    subject=f"{subscription.restaurant.name}: your OrderMama plan ends in {subscription.days_left} day(s)",
                    message=(
                        f"Your {subscription.plan.name} plan ends on {subscription.ends_at:%d %b %Y}.\n"
                        f"Renew from: {settings.SITE_URL}/dashboard/{subscription.restaurant.slug}/billing/\n"
                    ),
                    from_email=None, recipient_list=recipients,
                )
                sent += 1
            subscription.expiry_alert_sent_at = timezone.now()
            subscription.save(update_fields=["expiry_alert_sent_at"])
        self.stdout.write(self.style.SUCCESS(f"Expiry alerts sent: {sent}"))
