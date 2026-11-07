import re
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

RESERVED_SLUGS = {
    "dashboard", "superadmin", "register", "api", "payments", "static", "media",
    "ws", "django-admin", "admin", "login", "logout", "health", "merchant", "super-admin",
    "healthz",
}

hex_color = RegexValidator(r"^#[0-9a-fA-F]{6}$", "সঠিক হেক্স রং দিন (যেমন #E85D04)।")


def validate_image_size(f):
    if f.size > 4 * 1024 * 1024:
        raise ValidationError("ছবি সর্বোচ্চ ৪ MB হতে পারবে।")


class Restaurant(models.Model):
    class Theme(models.TextChoices):
        LIGHT = "light", "লাইট"
        DARK = "dark", "ডার্ক"

    class FontStyle(models.TextChoices):
        HIND = "hind", "Hind Siliguri"
        NOTO = "noto", "Noto Sans Bengali"

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=60, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=255, blank=True)

    # ব্র্যান্ডিং
    logo = models.ImageField(upload_to="logos/", blank=True, validators=[validate_image_size])
    cover_image = models.ImageField(upload_to="covers/", blank=True, validators=[validate_image_size])
    primary_color = models.CharField(max_length=7, default="#E85D04", validators=[hex_color])
    secondary_color = models.CharField(max_length=7, default="#FFF8F0", validators=[hex_color])
    theme = models.CharField(max_length=10, choices=Theme.choices, default=Theme.LIGHT)
    welcome_message = models.CharField(max_length=200, blank=True, default="স্বাগতম! আপনার পছন্দের খাবার বেছে নিন।")
    font_style = models.CharField(max_length=10, choices=FontStyle.choices, default=FontStyle.HIND)

    # বিলিং সেটিংস
    vat_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    service_charge_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    # সুপার অ্যাডমিনের নিয়ন্ত্রণ
    is_approved = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def clean(self):
        if self.slug and not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", self.slug):
            raise ValidationError({"slug": "স্লাগে শুধু ছোট হাতের ইংরেজি অক্ষর, সংখ্যা ও হাইফেন চলবে।"})
        if self.slug in RESERVED_SLUGS:
            raise ValidationError({"slug": "এই স্লাগটি সংরক্ষিত, অন্য একটি বেছে নিন।"})

    # --- সাবস্ক্রিপশন-নির্ভর হেল্পার ---
    @property
    def current_subscription(self):
        try:
            return self.subscription
        except Exception:
            return None

    @property
    def is_operational(self):
        """কাস্টমার ভিউ চালু থাকবে কি না: অনুমোদিত, ব্লক নয়, সাবস্ক্রিপশন সক্রিয় বা গ্রেস পিরিয়ডে।"""
        sub = self.current_subscription
        return bool(self.is_approved and not self.is_blocked and sub and sub.is_usable)

    def has_feature(self, feature):
        """feature: live_orders | qr_generator | branding"""
        sub = self.current_subscription
        if not (self.is_operational and sub):
            return False
        return bool(getattr(sub.plan, feature, False))


class Table(models.Model):
    # মাল্টি-টেনান্সি: প্রতিটি টেবিলে restaurant ফরেন কি
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="tables")
    number = models.PositiveIntegerField()
    # QR-এ বসে এই অনুমান-অযোগ্য UUID; নম্বর বদলে অন্য টেবিলে ঢোকা যায় না
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    label = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["restaurant_id", "number"]
        constraints = [
            models.UniqueConstraint(fields=["restaurant", "number"], name="uniq_table_number_per_restaurant")
        ]

    def __str__(self):
        return f"{self.restaurant.name} - টেবিল {self.number}"

    @property
    def display_name(self):
        return self.label or f"টেবিল {self.number}"
