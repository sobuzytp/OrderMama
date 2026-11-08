import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.restaurants.models import Restaurant
from apps.subscriptions.models import Plan


def new_tran_id():
    return "OM" + uuid.uuid4().hex[:18].upper()


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "অপেক্ষমাণ"
        SUBMITTED = "submitted", "জমা দেওয়া হয়েছে"
        APPROVED = "approved", "অনুমোদিত"
        REJECTED = "rejected", "প্রত্যাখ্যাত"
        PAID = "paid", "সফল"
        FAILED = "failed", "ব্যর্থ"
        CANCELLED = "cancelled", "বাতিল"

    class Method(models.TextChoices):
        BKASH = "bkash", "bKash"
        NAGAD = "nagad", "Nagad"
        ROCKET = "rocket", "Rocket"

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="payments")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gateway = models.CharField(max_length=20)
    tran_id = models.CharField(max_length=40, unique=True, default=new_tran_id)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    method = models.CharField(max_length=12, choices=Method.choices, blank=True)
    sender_number = models.CharField(max_length=20, blank=True)
    trx_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    rejection_reason = models.CharField(max_length=500, blank=True)
    gateway_ref = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant"], condition=Q(status="submitted"),
                name="one_submitted_payment_per_restaurant",
            ),
        ]

    def __str__(self):
        return f"{self.tran_id} {self.restaurant.name} ৳{self.amount}"

    def mark_paid(self, gateway_ref="", final_status=None):
        """আইডেম্পোটেন্ট: একই পেমেন্টে দুইবার মেয়াদ বাড়বে না।"""
        from django.db import transaction

        from apps.subscriptions.models import Subscription

        with transaction.atomic():
            pay = Payment.objects.select_for_update().get(pk=self.pk)
            if pay.status in (Payment.Status.PAID, Payment.Status.APPROVED):
                return pay
            pay.status = final_status or Payment.Status.PAID
            pay.paid_at = timezone.now()
            pay.gateway_ref = gateway_ref[:100]
            pay.save(update_fields=["status", "paid_at", "gateway_ref"])

            sub = Subscription.objects.select_for_update().filter(restaurant=pay.restaurant).first()
            if sub:
                sub.extend(plan=pay.plan)
            else:
                from datetime import timedelta

                Subscription.objects.create(
                    restaurant=pay.restaurant,
                    plan=pay.plan,
                    end_date=timezone.now() + timedelta(days=pay.plan.duration_days),
                )
            return pay
