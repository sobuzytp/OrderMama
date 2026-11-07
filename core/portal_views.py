import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .models import (
    Category, DiningTable, MenuItem, Order, PaymentTransaction, Plan, Restaurant,
    RestaurantMembership,
)

User = get_user_model()
PHONE_RE = re.compile(r"^\+?\d{10,15}$")
TRX_RE = re.compile(r"^[A-Za-z0-9]{6,40}$")


def platform_staff(user):
    return user.is_authenticated and user.is_staff


# ---------------------------------------------------------------------------
# Super Admin
# ---------------------------------------------------------------------------
@user_passes_test(platform_staff, login_url="/accounts/login/")
def control(request):
    restaurants = list(Restaurant.objects.all().order_by("-id"))
    expiring = []
    for restaurant in restaurants:
        restaurant.subscription = restaurant.current_subscription
        if restaurant.subscription and restaurant.subscription.expires_within(settings.SUBSCRIPTION_ALERT_DAYS):
            expiring.append(restaurant)
    return render(request, "control.html", {
        "restaurants": restaurants, "restaurant_count": len(restaurants),
        "active_count": sum(1 for r in restaurants if r.is_active),
        "user_count": User.objects.count(), "order_count": Order.objects.count(),
        "pending_payments": PaymentTransaction.objects.filter(status="pending").select_related("restaurant", "plan"),
        "expiring": expiring, "alert_days": settings.SUBSCRIPTION_ALERT_DAYS,
    })


@user_passes_test(platform_staff, login_url="/accounts/login/")
def create_restaurant(request):
    if request.method != "POST":
        return redirect("control")
    name = request.POST.get("name", "").strip()
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    email = request.POST.get("email", "").strip()
    try:
        count = int(request.POST.get("tables", "5"))
        if not name or not username or len(password) < 10 or count < 1 or count > 100:
            raise ValueError
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("control")
        base = slugify(name) or "restaurant"
        slug, suffix = base, 2
        while Restaurant.objects.filter(slug=slug).exists():
            slug, suffix = f"{base}-{suffix}", suffix + 1
        with transaction.atomic():
            restaurant = Restaurant.objects.create(name=name, slug=slug)
            owner = User.objects.create_user(username=username, email=email, password=password)
            RestaurantMembership.objects.create(restaurant=restaurant, user=owner, role="owner")
            DiningTable.objects.bulk_create(
                [DiningTable(restaurant=restaurant, number=n) for n in range(1, count + 1)]
            )
        messages.success(request, f"Restaurant {name} created. Owner username: {username}")
    except (ValueError, TypeError):
        messages.error(request, "Check the form. Password must be at least 10 characters and table count 1–100.")
    return redirect("control")


@user_passes_test(platform_staff, login_url="/accounts/login/")
@require_POST
def review_payment(request, pk, action):
    """Verify or reject a manual bKash/Nagad payment."""
    if action not in ("verify", "reject"):
        raise Http404
    payment = get_object_or_404(PaymentTransaction, pk=pk)
    try:
        if action == "verify":
            subscription = payment.verify(request.user)
            messages.success(request, f"Verified. {payment.restaurant} is active until {subscription.ends_at:%d %b %Y}.")
        else:
            payment.reject(request.user, request.POST.get("note", ""))
            messages.success(request, "Payment rejected.")
    except ValueError as error:
        messages.error(request, str(error))
    return redirect("control")


# ---------------------------------------------------------------------------
# Restaurant owner pages
# ---------------------------------------------------------------------------
def _owner_or_404(request, restaurant, roles=("owner", "manager")):
    membership = RestaurantMembership.objects.filter(user=request.user, restaurant=restaurant).first()
    if not request.user.is_staff and not (membership and membership.role in roles):
        raise Http404


def _limit_reached(restaurant, kind):
    """True when the active plan caps tables / menu items and the cap is reached."""
    subscription = restaurant.current_subscription
    if not subscription:
        return False
    if kind == "tables":
        cap, used = subscription.plan.max_tables, restaurant.tables.count()
    else:
        cap, used = subscription.plan.max_menu_items, restaurant.menu_items.count()
    return cap is not None and used >= cap


@login_required
def manage_restaurant(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    _owner_or_404(request, restaurant)
    if request.method == "POST":
        handle_manage_action(request, restaurant)
        return redirect("manage_restaurant", slug=slug)
    return render(request, "manage.html", {
        "restaurant": restaurant, "categories": restaurant.categories.all(),
        "items": restaurant.menu_items.select_related("category").all(),
        "tables": restaurant.tables.all(),
    })


def handle_manage_action(request, restaurant):
    action = request.POST.get("action")
    if action == "category":
        name = request.POST.get("name", "").strip()
        if name:
            Category.objects.create(restaurant=restaurant, name=name)
            messages.success(request, "Category created.")
    elif action in ("menu", "edit_item"):
        try:
            price = Decimal(request.POST.get("price", "0"))
            name = request.POST.get("name", "").strip()
            if not name or price <= 0 or price >= Decimal("100000000"):
                raise InvalidOperation
            if action == "menu":
                if _limit_reached(restaurant, "items"):
                    messages.error(request, "Your plan's menu item limit is reached. Please upgrade your plan.")
                    return
                category = get_object_or_404(Category, pk=request.POST.get("category"), restaurant=restaurant)
                MenuItem.objects.create(
                    restaurant=restaurant, category=category, name=name, price=price,
                    description=request.POST.get("description", "").strip(),
                )
                messages.success(request, "Menu item created.")
            else:
                item = get_object_or_404(MenuItem, pk=request.POST.get("item_id"), restaurant=restaurant)
                item.name, item.price = name, price
                item.description = request.POST.get("description", item.description).strip()
                item.save(update_fields=["name", "price", "description"])
                messages.success(request, "Menu item updated.")
        except (InvalidOperation, TypeError, ValueError):
            messages.error(request, "Enter a valid menu item and price.")
    elif action == "table":
        try:
            number = int(request.POST.get("number", "0"))
            if number < 1:
                raise ValueError
            if not restaurant.tables.filter(number=number).exists() and _limit_reached(restaurant, "tables"):
                messages.error(request, "Your plan's table limit is reached. Please upgrade your plan.")
                return
            DiningTable.objects.get_or_create(restaurant=restaurant, number=number)
            messages.success(request, "Table saved.")
        except (TypeError, ValueError):
            messages.error(request, "Enter a valid table number.")
    elif action == "toggle_item":
        item = get_object_or_404(MenuItem, pk=request.POST.get("item_id"), restaurant=restaurant)
        item.is_available = not item.is_available
        item.save(update_fields=["is_available"])
    elif action == "toggle_table":
        table = get_object_or_404(DiningTable, pk=request.POST.get("table_id"), restaurant=restaurant)
        table.is_active = not table.is_active
        table.save(update_fields=["is_active"])


@login_required
def billing(request, slug):
    """Subscription status and manual bKash/Nagad payment submission."""
    restaurant = get_object_or_404(Restaurant, slug=slug)
    _owner_or_404(request, restaurant, roles=("owner",))
    plans = Plan.objects.filter(active=True)
    if request.method == "POST":
        plan = plans.filter(pk=request.POST.get("plan") or 0).first()
        method = request.POST.get("method")
        phone = request.POST.get("sender_number", "").strip().replace(" ", "")
        trx = request.POST.get("trx_id", "").strip()
        if not plan or method not in ("bkash", "nagad"):
            messages.error(request, "Choose a plan and a payment method.")
        elif not PHONE_RE.match(phone) or not TRX_RE.match(trx):
            messages.error(request, "Enter the sender number and the Transaction ID exactly as in the SMS.")
        elif plan.monthly_price <= 0:
            messages.error(request, "This plan is free and does not need a payment.")
        else:
            try:
                with transaction.atomic():
                    PaymentTransaction.objects.create(
                        restaurant=restaurant, plan=plan, method=method, amount=plan.monthly_price,
                        sender_number=phone, trx_id=trx,
                    )
                messages.success(request, "Payment submitted. It will be activated after verification.")
            except IntegrityError:
                messages.error(request, "This Transaction ID has already been submitted.")
        return redirect("billing", slug=slug)
    return render(request, "billing.html", {
        "restaurant": restaurant, "plans": plans, "subscription": restaurant.current_subscription,
        "payments": restaurant.payments.select_related("plan")[:10],
        "bkash_number": settings.PAYMENT_BKASH_NUMBER, "nagad_number": settings.PAYMENT_NAGAD_NUMBER,
        "alert_days": settings.SUBSCRIPTION_ALERT_DAYS,
    })
