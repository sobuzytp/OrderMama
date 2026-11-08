import uuid

from django.db import models
from django.utils import timezone

from apps.restaurants.models import Restaurant
from apps.subscriptions.models import Plan


def new_tran_id():
    return "OM" + uuid.uuid4().hex[:18].upper()


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "অপেক্ষমাণ"
        PAID = "paid", "সফল"
        FAILED = "failed", "ব্যর্থ"
        CANCELLED = "cancelled", "বাতিল"

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="payments")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gateway = models.CharField(max_length=20)
    tran_id = models.CharField(max_length=40, unique=True, default=new_tran_id)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    gateway_ref = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.tran_id} {self.restaurant.name} ৳{self.amount}"

    def mark_paid(self, gateway_ref=""):
        """আইডেম্পোটেন্ট: একই পেমেন্টে দুইবার মেয়াদ বাড়বে না।"""
        from django.db import transaction

        from apps.subscriptions.models import Subscription

        with transaction.atomic():
            pay = Payment.objects.select_for_update().get(pk=self.pk)
            if pay.status == Payment.Status.PAID:
                return pay
            pay.status = Payment.Status.PAID
            pay.paid_at = timezone.now()
            pay.gateway_ref = gateway_ref[:100]
            pay.save()

            sub = Subscription.objects.select_for_update().filter(restaurant=pay.restaurant).first()
            if sub:
                sub.extend(plan=pay.plan)
            else:
                from datetime import timedelta

                Subscription.objects.create(
                    restaurant=pay.restaurant,
                    plan=pay.plan,
                    end_date=timezone.now() + timedelta(days=pay.plan.duration_days),
                    grace_days=pay.plan.grace_days,
                )
            return pay
