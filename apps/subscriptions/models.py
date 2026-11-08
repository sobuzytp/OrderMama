from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.restaurants.models import Restaurant


class Plan(models.Model):
    # কোডটি ডাইনামিক রাখা হয়েছে, যাতে সুপার অ্যাডমিন নতুন প্ল্যান যোগ করতে পারেন।
    code = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    grace_days = models.PositiveIntegerField(default=3)

    # প্রতিটি ফিচার আলাদাভাবে চালু/বন্ধ করা যায়।
    live_orders = models.BooleanField(default=False)
    qr_generator = models.BooleanField(default=False)
    branding = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["price", "name"]

    def __str__(self):
        return f"{self.name} (৳{self.price})"


class Subscription(models.Model):
    restaurant = models.OneToOneField(Restaurant, on_delete=models.CASCADE, related_name="subscription")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    grace_days = models.PositiveIntegerField(default=3)
    warning_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.restaurant.name} - {self.plan.name}"

    @property
    def grace_end(self):
        return self.end_date + timedelta(days=self.grace_days)

    @property
    def is_active(self):
        return timezone.now() <= self.end_date

    @property
    def in_grace(self):
        now = timezone.now()
        return self.end_date < now <= self.grace_end

    @property
    def is_usable(self):
        """মেয়াদ বা গ্রেস পিরিয়ডের মধ্যে থাকলে কাস্টমার ভিউ চালু।"""
        return timezone.now() <= self.grace_end

    @property
    def days_left(self):
        return (self.end_date - timezone.now()).days

    @property
    def expiring_soon(self):
        return self.is_active and self.end_date - timezone.now() <= timedelta(
            days=settings.SUBSCRIPTION_WARNING_DAYS
        )

    @property
    def state(self):
        if self.is_active:
            return "expiring" if self.expiring_soon else "active"
        return "grace" if self.in_grace else "expired"

    def extend(self, plan=None, days=None):
        """মেয়াদ থাকলে তার শেষ থেকে, শেষ হয়ে গেলে এখন থেকে দিন যোগ হয়।"""
        if plan:
            self.plan = plan
            self.grace_days = plan.grace_days
        days = self.plan.duration_days if days is None else days
        base = max(self.end_date, timezone.now())
        self.end_date = base + timedelta(days=days)
        self.warning_sent_at = None
        self.save()
        return self
