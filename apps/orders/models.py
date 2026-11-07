from decimal import ROUND_HALF_UP, Decimal

from django.db import models, transaction
from django.utils import timezone

from apps.menu.models import MenuItem
from apps.restaurants.models import Restaurant, Table

TWO = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(TWO, rounding=ROUND_HALF_UP)


class Bill(models.Model):
    """একই টেবিলের সবার অর্ডার একটি খোলা বিলে জমা হয়।"""

    class Status(models.TextChoices):
        OPEN = "open", "খোলা"
        REQUESTED = "requested", "বিল চাওয়া হয়েছে"
        PAID = "paid", "পরিশোধিত"

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="bills")
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="bills")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    opened_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]
        constraints = [
            # একটি টেবিলে একসাথে একটাই অপরিশোধিত বিল
            models.UniqueConstraint(
                fields=["table"],
                condition=~models.Q(status="paid"),
                name="uniq_unpaid_bill_per_table",
            )
        ]

    def __str__(self):
        return f"বিল #{self.pk} - {self.table}"

    @classmethod
    def open_for_table(cls, table):
        bill = cls.objects.filter(table=table).exclude(status=cls.Status.PAID).first()
        if bill:
            return bill
        return cls.objects.create(restaurant=table.restaurant, table=table)

    def totals(self):
        subtotal = sum(
            (o.subtotal for o in self.orders.exclude(status=Order.Status.REJECTED)), Decimal("0")
        )
        vat = money(subtotal * self.restaurant.vat_percent / 100)
        service = money(subtotal * self.restaurant.service_charge_percent / 100)
        return {
            "subtotal": money(subtotal),
            "vat": vat,
            "service_charge": service,
            "total": money(subtotal + vat + service),
        }

    @transaction.atomic
    def mark_paid(self):
        now = timezone.now()
        for order in self.orders.exclude(status__in=[Order.Status.REJECTED, Order.Status.PAID]):
            order.status = Order.Status.PAID
            order.save(update_fields=["status", "updated_at"])
        self.status = self.Status.PAID
        self.paid_at = now
        self.save(update_fields=["status", "paid_at"])


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "পেন্ডিং"
        ACCEPTED = "accepted", "গৃহীত"
        PREPARING = "preparing", "রান্না হচ্ছে"
        READY = "ready", "রেডি"
        SERVED = "served", "পরিবেশিত"
        PAID = "paid", "পরিশোধিত"
        REJECTED = "rejected", "বাতিল"

    # কোন স্ট্যাটাস থেকে কোথায় যাওয়া যাবে
    TRANSITIONS = {
        "pending": {"accepted", "rejected"},
        "accepted": {"preparing", "rejected"},
        "preparing": {"ready", "rejected"},
        "ready": {"served"},
        "served": {"paid"},
        "paid": set(),
        "rejected": set(),
    }
    ACTIVE_STATUSES = ["pending", "accepted", "preparing", "ready"]

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="orders")
    table = models.ForeignKey(Table, on_delete=models.PROTECT, related_name="orders")
    bill = models.ForeignKey(Bill, on_delete=models.PROTECT, related_name="orders")
    customer_name = models.CharField(max_length=80)
    customer_phone = models.CharField(max_length=20)
    note = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    reject_reason = models.CharField(max_length=200, blank=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["restaurant", "status", "created_at"])]

    def __str__(self):
        return f"অর্ডার #{self.pk}"

    def can_move_to(self, new_status):
        return new_status in self.TRANSITIONS.get(self.status, set())

    def recalc(self):
        self.subtotal = money(sum((i.line_total for i in self.items.all()), Decimal("0")))
        self.save(update_fields=["subtotal", "updated_at"])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, null=True, on_delete=models.SET_NULL, related_name="+")
    # নাম ও দামের স্ন্যাপশট: পরে মেনুর দাম বদলালেও পুরনো অর্ডার ঠিক থাকবে
    name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    note = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.name}"

    @property
    def line_total(self):
        return money(self.unit_price * self.quantity)


class ServiceRequest(models.Model):
    class Kind(models.TextChoices):
        WAITER = "waiter", "ওয়েটার ডাকা"
        BILL = "bill", "বিল রিকোয়েস্ট"

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="service_requests")
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="service_requests")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} - {self.table}"
