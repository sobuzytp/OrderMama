import hashlib
import io
import json
from decimal import Decimal

import qrcode
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Max, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import localdate
from django.views.decorators.http import require_POST
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .models import (
    DiningTable, MenuItem, Order, OrderItem, Restaurant, RestaurantMembership, ServiceRequest,
)

STAFF_ROLES = ["owner", "manager", "cashier", "kitchen"]
DASHBOARD_ROLES = ["owner", "manager", "cashier"]
STATUS_FLOW = {
    "pending": ["accepted", "rejected"], "accepted": ["preparing"],
    "preparing": ["ready"], "ready": ["served"], "served": ["paid"],
}
# Customer-facing progress steps (index used by the tracking page).
TRACK_STEPS = {"pending": 0, "accepted": 1, "preparing": 2, "ready": 3, "served": 4, "paid": 4}
MAX_CART_ROWS, MAX_QTY, MAX_NOTE = 30, 20, 250


def wants_json(request):
    return request.headers.get("x-requested-with") == "fetch"


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
def home(request):
    return render(request, "home.html")


def demo_menu(request):
    return render(request, "demo_menu.html")


def parse_cart(raw):
    """Validate the cart JSON sent by the browser.

    Returns {menu_item_id: {"qty": int, "note": str}}; raises ValueError when invalid.
    Prices are never read from the browser.
    """
    rows = json.loads(raw or "[]")
    if not isinstance(rows, list) or not rows or len(rows) > MAX_CART_ROWS:
        raise ValueError("rows")
    cart = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("row")
        item_id, qty = int(row["id"]), int(row.get("qty", 1))
        if item_id <= 0 or qty < 1 or qty > MAX_QTY:
            raise ValueError("qty")
        note = str(row.get("note", "") or "").strip()[:MAX_NOTE]
        entry = cart.setdefault(item_id, {"qty": 0, "note": ""})
        entry["qty"] = min(MAX_QTY, entry["qty"] + qty)
        if note and note not in entry["note"]:
            entry["note"] = (entry["note"] + "; " + note).strip("; ")[:MAX_NOTE]
    return cart


def place_order(request, restaurant, table):
    """Handle a customer's order POST and return the HTTP response."""
    if not restaurant.accepts_orders():
        return HttpResponse("এই মুহূর্তে অর্ডার নেওয়া বন্ধ আছে", status=403)
    name = request.POST.get("name", "").strip()
    phone = request.POST.get("phone", "").strip()
    if not name or len(name) > 100 or len(phone) < 7 or len(phone) > 20:
        return HttpResponse("সঠিক নাম ও মোবাইল নম্বর দিন", status=400)
    try:
        cart = parse_cart(request.POST.get("items", "[]"))
    except (TypeError, ValueError, KeyError, OverflowError):
        return HttpResponse("কার্টের তথ্য সঠিক নয় (সর্বোচ্চ ৩০টি খাবার)", status=400)

    with transaction.atomic():
        items = list(MenuItem.objects.select_for_update().filter(
            id__in=cart, restaurant=restaurant, is_available=True,
            category__restaurant=restaurant, category__is_active=True,
        ))
        if len(items) != len(cart):
            return HttpResponse("এক বা একাধিক খাবার আর উপলব্ধ নেই", status=400)
        order = Order.objects.create(
            restaurant=restaurant, table=table, customer_name=name, customer_phone=phone,
        )
        total = Decimal("0.00")
        for item in items:
            line = cart[item.pk]
            OrderItem.objects.create(
                order=order, menu_item=item, item_name=item.name, unit_price=item.price,
                quantity=line["qty"], note=line["note"],
            )
            total += item.price * line["qty"]
        order.total = total
        order.save(update_fields=["total"])
    return redirect("track", slug=restaurant.slug, token=order.public_token)


def render_menu(request, restaurant, table):
    if request.method == "POST":
        return place_order(request, restaurant, table)
    categories = restaurant.categories.filter(is_active=True).prefetch_related("items")
    args = {"slug": restaurant.slug, "token": table.token}
    return render(request, "menu.html", {
        "restaurant": restaurant, "table": table, "categories": categories,
        "ordering_open": restaurant.accepts_orders(),
        "waiter_url": reverse("service_by_token", kwargs={**args, "kind": "waiter"}),
        "bill_url": reverse("service_by_token", kwargs={**args, "kind": "bill"}),
    })


def menu_by_token(request, slug, token):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    table = get_object_or_404(DiningTable, restaurant=restaurant, token=token, is_active=True)
    return render_menu(request, restaurant, table)


def menu(request, slug, number):
    """Older table-number URL, kept so already-printed QR codes keep working."""
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    table = get_object_or_404(DiningTable, restaurant=restaurant, number=number, is_active=True)
    return render_menu(request, restaurant, table)


def track(request, slug, token):
    order = get_object_or_404(
        Order.objects.select_related("table", "restaurant").prefetch_related("items"),
        restaurant__slug=slug, public_token=token,
    )
    kinds = {k: reverse("service_by_token", kwargs={"slug": slug, "token": order.table.token, "kind": k})
             for k in ("waiter", "bill")}
    return render(request, "track.html", {
        "order": order, "restaurant": order.restaurant, "waiter_url": kinds["waiter"],
        "bill_url": kinds["bill"], "step": TRACK_STEPS.get(order.status, 0),
        "poll_ms": settings.LIVE_POLL_SECONDS * 1000,
    })


def track_status(request, slug, token):
    order = get_object_or_404(Order, restaurant__slug=slug, public_token=token)
    return JsonResponse({
        "status": order.status, "label": order.get_status_display(),
        "step": TRACK_STEPS.get(order.status, 0), "rejected": order.status == "rejected",
    })


def create_service_request(restaurant, table, kind):
    """One open request per kind per table, so repeated taps don't spam the kitchen."""
    existing = ServiceRequest.objects.filter(restaurant=restaurant, table=table, kind=kind, resolved=False).first()
    if existing:
        return existing, False
    return ServiceRequest.objects.create(restaurant=restaurant, table=table, kind=kind), True


def _service_response(request, created, fallback_name, **kwargs):
    if wants_json(request):
        return JsonResponse({"ok": True, "created": created})
    return redirect(fallback_name, **kwargs)


@require_POST
def service_by_token(request, slug, token, kind):
    if kind not in ("waiter", "bill"):
        raise Http404
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    table = get_object_or_404(DiningTable, restaurant=restaurant, token=token, is_active=True)
    _, created = create_service_request(restaurant, table, kind)
    return _service_response(request, created, "menu_by_token", slug=slug, token=token)


@require_POST
def service(request, slug, number, kind):
    if kind not in ("waiter", "bill"):
        raise Http404
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    table = get_object_or_404(DiningTable, restaurant=restaurant, number=number, is_active=True)
    _, created = create_service_request(restaurant, table, kind)
    return _service_response(request, created, "menu", slug=slug, number=number)


# ---------------------------------------------------------------------------
# Restaurant staff
# ---------------------------------------------------------------------------
def member(user, restaurant):
    return RestaurantMembership.objects.filter(user=user, restaurant=restaurant).first()


def require_role(user, restaurant, roles):
    membership = member(user, restaurant)
    return bool(user.is_staff or (membership and membership.role in roles))


@login_required
def dashboard(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, DASHBOARD_ROLES):
        raise Http404
    today = restaurant.orders.filter(created_at__date=localdate())
    sales = today.filter(status__in=["served", "paid"]).aggregate(v=Sum("total"))["v"] or 0
    subscription = restaurant.current_subscription
    return render(request, "dashboard.html", {
        "restaurant": restaurant, "orders": restaurant.orders.select_related("table")[:20],
        "count": today.count(), "sales": sales, "subscription": subscription,
        "expiring": bool(subscription and subscription.expires_within(settings.SUBSCRIPTION_ALERT_DAYS)),
        "can_manage": require_role(request.user, restaurant, ["owner", "manager"]),
    })


def board_context(restaurant):
    orders = list(restaurant.orders.filter(status__in=Order.ACTIVE_STATUSES)
                  .select_related("table").prefetch_related("items").order_by("created_at"))
    services = list(restaurant.service_requests.filter(resolved=False).select_related("table").order_by("created_at"))
    return orders, services


@login_required
def kot(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, STAFF_ROLES):
        raise Http404
    orders, services = board_context(restaurant)
    return render(request, "kot.html", {
        "restaurant": restaurant, "orders": orders, "services": services,
        "poll_ms": settings.LIVE_POLL_SECONDS * 1000,
    })


def live_feed(request, slug):
    """JSON snapshot used by the KOT screen (polling fallback for WebSocket)."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "auth"}, status=401)
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, STAFF_ROLES):
        raise Http404
    orders, services = board_context(restaurant)
    html = render_to_string("partials/kot_board.html", {
        "restaurant": restaurant, "orders": orders, "services": services,
    }, request=request)
    latest = restaurant.orders.aggregate(m=Max("id"))["m"] or 0
    return JsonResponse({
        "latest_order_id": latest,
        "pending_count": sum(1 for o in orders if o.status == "pending"),
        "service_ids": [s.pk for s in services],
        "signature": hashlib.md5(html.encode()).hexdigest(),
        "html": html,
    })


@login_required
@require_POST
def status(request, slug, pk):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, STAFF_ROLES):
        raise Http404
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    new_status = request.POST.get("status")
    if new_status in STATUS_FLOW.get(order.status, []):
        order.status = new_status
        order.save(update_fields=["status"])
    if wants_json(request):
        return JsonResponse({"ok": True, "status": order.status})
    return redirect("kot", slug=slug)


@login_required
@require_POST
def resolve_service(request, slug, pk):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, STAFF_ROLES):
        raise Http404
    get_object_or_404(ServiceRequest, pk=pk, restaurant=restaurant).resolve()
    if wants_json(request):
        return JsonResponse({"ok": True})
    return redirect("kot", slug=slug)


@login_required
def qr_pdf(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, ["owner", "manager"]):
        raise Http404
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for index, table in enumerate(restaurant.tables.filter(is_active=True)):
        if index and index % 4 == 0:
            pdf.showPage()
        image_buffer = io.BytesIO()
        qrcode.make(table.qr_url()).save(image_buffer, format="PNG")
        image_buffer.seek(0)
        x = 45 + (index % 2) * 270
        y = 680 - ((index % 4) // 2) * 360
        pdf.drawImage(ImageReader(image_buffer), x, y, width=140, height=140)
        pdf.drawString(x, y - 20, f"{restaurant.name} - Table {table.number}")
    pdf.save()
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{slug}-qr.pdf"'
    return response
