"""
OrderMama data model.

Every restaurant-owned table has a `restaurant` foreign key, which is what makes
the platform multi-tenant: all staff/customer queries are filtered by it.

Existing field names are kept unchanged so that data in a live database
survives the migration; new fields are nullable or have defaults.
"""
import math
import uuid
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

PRICE_MIN = MinValueValidator(Decimal("0.01"))
HEX_COLOR = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Use a hex colour such as #E85D04.")


# ---------------------------------------------------------------------------
# Tenant (restaurant) and its people
# ---------------------------------------------------------------------------
class Restaurant(models.Model):
    THEMES = [("light", "Light"), ("dark", "Dark")]

    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True, help_text="Used in URLs: /r/<slug>/…")
    subdomain = models.SlugField(
        max_length=63, unique=True, null=True, blank=True,
        help_text="Optional future subdomain, e.g. 'dhaka-grill' → dhaka-grill.example.com",
    )
    logo = models.ImageField(upload_to="logos/", blank=True, null=True)
    cover_image = models.ImageField(upload_to="covers/", blank=True, null=True)
    primary_color = models.CharField(max_length=7, default="#E85D04", validators=[HEX_COLOR])
    secondary_color = models.CharField(max_length=7, default="#292522", validators=[HEX_COLOR])
    theme = models.CharField(max_length=8, choices=THEMES, default="light")
    welcome_message = models.CharField(max_length=200, default="স্বাগতম!")
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def current_subscription(self):
        """Latest-ending active subscription, or None."""
        return self.subscriptions.filter(active=True).order_by("-ends_at").first()

    @property
    def has_active_access(self):
        """True while the subscription is valid or still inside its grace days."""
        subscription = self.current_subscription
        return bool(subscription and subscription.in_grace)

    def accepts_orders(self):
        """Customer ordering is open if the shop is active and (when enforced) paid up."""
        if not self.is_active:
            return False
        if getattr(settings, "ENFORCE_SUBSCRIPTIONS", False):
            return self.has_active_access
        return True


class RestaurantMembership(models.Model):
    ROLES = [
        ("owner", "Owner"), ("manager", "Manager"), ("cashier", "Cashier"),
        ("kitchen", "Kitchen"), ("waiter", "Waiter"),
    ]

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=ROLES)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["restaurant", "user"], name="unique_restaurant_user"),
        ]

    def __str__(self):
        return f"{self.user} — {self.get_role_display()} @ {self.restaurant}"


class DiningTable(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="tables")
    number = models.PositiveIntegerField()
    # Unguessable id embedded in the QR URL, so customers cannot hop to other tables.
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["restaurant", "number"]
        constraints = [
            models.UniqueConstraint(fields=["restaurant", "number"], name="unique_restaurant_table"),
        ]

    def __str__(self):
        return f"{self.restaurant} — Table {self.number}"

    def get_absolute_url(self):
        """Secure customer URL (used in QR codes)."""
        return reverse("menu_by_token", kwargs={"slug": self.restaurant.slug, "token": self.token})

    def qr_url(self):
        return f"{settings.SITE_URL}{self.get_absolute_url()}"


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------
class Category(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=100)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return f"{self.name} ({self.restaurant})"


class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="menu_items")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="menu/", blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[PRICE_MIN])
    is_vegetarian = models.BooleanField(default=True)
    # In stock / out of stock toggle used by the owner.
    is_available = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return f"{self.name} — ৳{self.price}"

    def clean(self):
        if self.category_id and self.restaurant_id and self.category.restaurant_id != self.restaurant_id:
            raise ValidationError("Category belongs to a different restaurant.")


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------
class Order(models.Model):
    STATUSES = [
        ("pending", "Pending"), ("accepted", "Accepted"), ("preparing", "Cooking"),
        ("ready", "Ready"), ("served", "Served"), ("paid", "Paid"), ("rejected", "Rejected"),
    ]
    ACTIVE_STATUSES = ["pending", "accepted", "preparing", "ready"]

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="orders")
    table = models.ForeignKey(DiningTable, on_delete=models.PROTECT, related_name="orders")
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20)
    status = models.CharField(max_length=12, choices=STATUSES, default="pending")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    public_token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["restaurant", "status"], name="order_rest_status_idx"),
            models.Index(fields=["restaurant", "-created_at"], name="order_rest_created_idx"),
        ]

    def __str__(self):
        return f"Order #{self.pk} · {self.restaurant} · Table {self.table.number}"

    def clean(self):
        if self.table_id and self.restaurant_id and self.table.restaurant_id != self.restaurant_id:
            raise ValidationError("Table belongs to a different restaurant.")

    def recalculate_total(self, save=True):
        self.total = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        if save:
            self.save(update_fields=["total"])
        return self.total


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    # Name and price are copied so later menu edits never change past orders.
    item_name = models.CharField(max_length=140)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.CharField(max_length=250, blank=True, help_text='e.g. "Less spicy"')

    def __str__(self):
        return f"{self.item_name} × {self.quantity}"

    @property
    def line_total(self):
        return self.unit_price * self.quantity


class ServiceRequest(models.Model):
    KINDS = [("waiter", "Waiter"), ("bill", "Bill")]

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="service_requests")
    table = models.ForeignKey(DiningTable, on_delete=models.CASCADE, related_name="service_requests")
    kind = models.CharField(max_length=10, choices=KINDS)
    created_at = models.DateTimeField(default=timezone.now)
    resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        state = "done" if self.resolved else "open"
        return f"{self.get_kind_display()} · Table {self.table.number} ({state})"

    def resolve(self):
        if not self.resolved:
            self.resolved = True
            self.resolved_at = timezone.now()
            self.save(update_fields=["resolved", "resolved_at"])


# ---------------------------------------------------------------------------
# Monetisation: plans, subscriptions, manual bKash/Nagad payments
# ---------------------------------------------------------------------------
class Plan(models.Model):
    name = models.CharField(max_length=80)
    # Price for one `duration_days` period (field name kept for existing data).
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    duration_days = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    max_tables = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = unlimited")
    max_menu_items = models.PositiveIntegerField(null=True, blank=True, help_text="Empty = unlimited")
    live_orders = models.BooleanField(default=False)
    branding = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["monthly_price", "name"]

    def __str__(self):
        return f"{self.name} (৳{self.monthly_price} / {self.duration_days} days)"


class Subscription(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    grace_days = models.PositiveSmallIntegerField(default=3)
    active = models.BooleanField(default=True)
    expiry_alert_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-ends_at"]

    def __str__(self):
        return f"{self.restaurant} · {self.plan.name} until {self.ends_at:%Y-%m-%d}"

    @property
    def in_grace(self):
        """Still allowed to operate: not expired, or expired only within grace days."""
        return self.active and timezone.now() <= self.ends_at + timedelta(days=self.grace_days)

    @property
    def is_expired(self):
        return timezone.now() > self.ends_at

    @property
    def days_left(self):
        seconds = (self.ends_at - timezone.now()).total_seconds()
        return max(0, math.ceil(seconds / 86400))

    @property
    def status(self):
        if not self.active:
            return "cancelled"
        if not self.is_expired:
            return "active"
        return "grace" if self.in_grace else "expired"

    def expires_within(self, days):
        return self.active and not self.is_expired and self.ends_at <= timezone.now() + timedelta(days=days)

    @classmethod
    def start(cls, restaurant, plan, days=None):
        """Create a subscription; if one is still running, extend from its end date."""
        days = days or plan.duration_days
        current = restaurant.current_subscription
        now = timezone.now()
        begins = current.ends_at if current and current.ends_at > now else now
        return cls.objects.create(
            restaurant=restaurant, plan=plan, starts_at=begins, ends_at=begins + timedelta(days=days),
        )


class PaymentTransaction(models.Model):
    """A subscription payment sent by a restaurant via mobile banking.

    Today the Super Admin verifies the TrxID by hand. The `gateway_*` fields are
    reserved for a future automatic bKash/Nagad API integration.
    """

    METHODS = [("bkash", "bKash"), ("nagad", "Nagad"), ("other", "Other")]
    STATUSES = [("pending", "Pending"), ("verified", "Verified"), ("rejected", "Rejected")]

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="payments")
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="payments")
    method = models.CharField(max_length=10, choices=METHODS)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[PRICE_MIN])
    sender_number = models.CharField(max_length=20)
    trx_id = models.CharField("Transaction ID", max_length=40)
    status = models.CharField(max_length=10, choices=STATUSES, default="pending")
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=250, blank=True)
    subscription = models.ForeignKey(
        Subscription, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments",
    )
    # Reserved for future automatic gateway integration.
    gateway_payment_id = models.CharField(max_length=80, blank=True)
    gateway_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            # A TrxID can only be used once, unless the earlier claim was rejected.
            models.UniqueConstraint(
                fields=["method", "trx_id"], condition=~Q(status="rejected"), name="unique_active_trx_per_method",
            ),
        ]

    def __str__(self):
        return f"{self.get_method_display()} {self.trx_id} · ৳{self.amount} · {self.get_status_display()}"

    def save(self, *args, **kwargs):
        self.trx_id = (self.trx_id or "").strip().upper()
        super().save(*args, **kwargs)

    @transaction.atomic
    def verify(self, user=None):
        """Mark as paid and start/extend the subscription."""
        payment = PaymentTransaction.objects.select_for_update().get(pk=self.pk)
        if payment.status != "pending":
            raise ValueError("Only pending payments can be verified.")
        subscription = Subscription.start(payment.restaurant, payment.plan)
        payment.status = "verified"
        payment.reviewed_by = user
        payment.reviewed_at = timezone.now()
        payment.subscription = subscription
        payment.save()
        self.__dict__.update(payment.__dict__)
        return subscription

    @transaction.atomic
    def reject(self, user=None, note=""):
        payment = PaymentTransaction.objects.select_for_update().get(pk=self.pk)
        if payment.status != "pending":
            raise ValueError("Only pending payments can be rejected.")
        payment.status = "rejected"
        payment.reviewed_by = user
        payment.reviewed_at = timezone.now()
        payment.review_note = note[:250]
        payment.save()
        self.__dict__.update(payment.__dict__)
