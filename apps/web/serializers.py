import re

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from apps.accounts.models import User
from apps.menu.models import Category, MenuItem
from apps.restaurants.models import RESERVED_SLUGS, Restaurant, Table
from apps.subscriptions.models import Plan, Subscription

from .utils import compress_image

PHONE_RE = re.compile(r"^(?:\+?88)?01[3-9]\d{8}$")


# ---------- কাস্টমার ----------
class OrderLineSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    qty = serializers.IntegerField(min_value=1, max_value=50)
    note = serializers.CharField(max_length=200, allow_blank=True, required=False, default="")


class OrderCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=80)
    customer_phone = serializers.CharField(max_length=20)
    note = serializers.CharField(max_length=300, allow_blank=True, required=False, default="")
    items = OrderLineSerializer(many=True, allow_empty=False, max_length=40)

    def validate_customer_name(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("নাম দিন।")
        return v

    def validate_customer_phone(self, v):
        v = re.sub(r"[\s-]", "", v)
        if not PHONE_RE.match(v):
            raise serializers.ValidationError("সঠিক মোবাইল নম্বর দিন (যেমন 01712345678)।")
        return v


# ---------- মেনু ----------
class CategorySerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(source="items.count", read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "position", "is_active", "items_count"]


class MenuItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    image = serializers.ImageField(write_only=True, required=False, allow_null=True)
    remove_image = serializers.BooleanField(write_only=True, required=False, default=False)
    discount_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            "id", "category", "name", "description", "price", "compare_at_price", "discount_percent", "image", "image_url", "remove_image",
            "is_veg", "is_stock_out", "is_active", "position",
        ]

    def get_image_url(self, obj):
        return obj.image.url if obj.image else ""

    def validate_category(self, cat):
        if cat.restaurant_id != self.context["restaurant"].pk:
            raise serializers.ValidationError("ক্যাটাগরি পাওয়া যায়নি।")
        return cat

    def validate_price(self, v):
        if v < 0 or v > 1_000_000:
            raise serializers.ValidationError("দাম সঠিক নয়।")
        return v

    def validate_image(self, f):
        return compress_image(f) if f else f

    def update(self, instance, validated):
        if validated.pop("remove_image", False):
            instance.image.delete(save=False)
            instance.image = ""
        return super().update(instance, validated)

    def create(self, validated):
        validated.pop("remove_image", None)
        return super().create(validated)


class TableSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = ["id", "number", "label", "is_active", "token", "url"]
        read_only_fields = ["number", "token"]

    def get_url(self, obj):
        from django.conf import settings
        return f"{settings.SITE_BASE_URL}/{obj.restaurant.slug}/{obj.token}/"


class BrandingSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(required=False, allow_null=True)
    cover_image = serializers.ImageField(required=False, allow_null=True)
    logo_url = serializers.SerializerMethodField()
    cover_url = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = [
            "name", "phone", "address", "logo", "cover_image", "logo_url", "cover_url",
            "primary_color", "secondary_color", "theme", "welcome_message", "font_style",
            "vat_percent", "service_charge_percent",
        ]

    def get_logo_url(self, o):
        return o.logo.url if o.logo else ""

    def get_cover_url(self, o):
        return o.cover_image.url if o.cover_image else ""

    def validate_logo(self, f):
        return compress_image(f, max_side=512) if f else f

    def validate_cover_image(self, f):
        return compress_image(f, max_side=1600) if f else f

    def validate_vat_percent(self, v):
        if v < 0 or v > 100:
            raise serializers.ValidationError("০ থেকে ১০০ এর মধ্যে দিন।")
        return v

    validate_service_charge_percent = validate_vat_percent


class StaffSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=8)
    role = serializers.ChoiceField(
        choices=[c for c in User.Role.choices if c[0] != User.Role.OWNER]
    )

    class Meta:
        model = User
        fields = ["id", "username", "first_name", "phone", "role", "is_active", "password"]

    def validate_password(self, v):
        validate_password(v)
        return v

    def validate(self, attrs):
        if self.instance is None and "password" not in attrs:
            raise serializers.ValidationError({"password": "পাসওয়ার্ড দিন।"})
        return attrs

    def create(self, validated):
        pw = validated.pop("password")
        user = User(restaurant=self.context["restaurant"], **validated)
        user.set_password(pw)
        user.save()
        return user

    def update(self, instance, validated):
        pw = validated.pop("password", None)
        for k, v in validated.items():
            setattr(instance, k, v)
        if pw:
            instance.set_password(pw)
        instance.save()
        return instance


# ---------- রেজিস্ট্রেশন ----------
class RegisterSerializer(serializers.Serializer):
    restaurant_name = serializers.CharField(max_length=120)
    slug = serializers.SlugField(max_length=60)
    phone = serializers.CharField(max_length=20)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=8, write_only=True)

    def validate_slug(self, v):
        v = v.lower()
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise serializers.ValidationError("শুধু ছোট হাতের ইংরেজি অক্ষর, সংখ্যা ও হাইফেন।")
        if v in RESERVED_SLUGS or Restaurant.objects.filter(slug=v).exists():
            raise serializers.ValidationError("এই স্লাগটি নেওয়া আছে, অন্যটি দিন।")
        return v

    def validate_phone(self, v):
        v = re.sub(r"[\s-]", "", v)
        if not PHONE_RE.match(v):
            raise serializers.ValidationError("সঠিক মোবাইল নম্বর দিন।")
        return v

    def validate_username(self, v):
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError("এই ইউজারনেম নেওয়া আছে।")
        return v

    def validate_password(self, v):
        validate_password(v)
        return v

    @transaction.atomic
    def create(self, validated):
        r = Restaurant.objects.create(
            name=validated["restaurant_name"], slug=validated["slug"], phone=validated["phone"]
        )
        User.objects.create_user(
            username=validated["username"], password=validated["password"],
            restaurant=r, role=User.Role.OWNER, phone=validated["phone"],
        )
        return r


# ---------- সুপার অ্যাডমিন ----------
class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "code", "name", "price", "duration_days", "live_orders",
                  "qr_generator", "branding", "is_active"]
        read_only_fields = ["code", "name"]

    def validate_price(self, value):
        if value < 0 or value > 99999999.99:
            raise serializers.ValidationError("প্ল্যানের দাম ০ থেকে ৯৯,৯৯৯,৯৯৯.৯৯ টাকার মধ্যে হতে হবে।")
        return value

    def validate_duration_days(self, value):
        if not 1 <= value <= 3650:
            raise serializers.ValidationError("প্ল্যানের মেয়াদ ১ থেকে ৩৬৫০ দিনের মধ্যে হতে হবে।")
        return value


def restaurant_admin_row(r):
    sub = r.current_subscription
    owner = r.staff.filter(role=User.Role.OWNER).first()
    return {
        "id": r.pk, "name": r.name, "slug": r.slug, "phone": r.phone,
        "is_approved": r.is_approved, "is_blocked": r.is_blocked,
        "owner": owner.username if owner else "",
        "created_at": r.created_at.isoformat(),
        "plan": sub.plan.name if sub else "",
        "plan_code": sub.plan.code if sub else "",
        "end_date": sub.end_date.isoformat() if sub else None,
        "days_left": sub.days_left if sub else None,
        "state": sub.state if sub else "none",
    }
