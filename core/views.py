import io
import json
from decimal import Decimal, InvalidOperation
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import qrcode
from .models import (
    Category, DiningTable, MenuItem, Order, OrderItem, Restaurant,
    RestaurantMembership, ServiceRequest,
)

def home(request):
    return render(request, "home.html")

def menu(request, slug, number):
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    table = get_object_or_404(DiningTable, restaurant=restaurant, number=number, is_active=True)
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        try:
            rows = json.loads(request.POST.get("items", "[]"))
        except (TypeError, ValueError):
            rows = None
        if not name or len(name) > 100 or len(phone) < 7 or len(phone) > 20:
            return HttpResponse("সঠিক নাম ও মোবাইল নম্বর দিন", status=400)
        if not isinstance(rows, list) or not rows or len(rows) > 30:
            return HttpResponse("সর্বোচ্চ ৩০টি খাবার নির্বাচন করুন", status=400)
        quantities = {}
        try:
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError
                item_id = int(row["id"])
                qty = int(row.get("qty", 1))
                if item_id <= 0 or qty < 1 or qty > 20:
                    raise ValueError
                quantities[item_id] = min(20, quantities.get(item_id, 0) + qty)
        except (KeyError, TypeError, ValueError, OverflowError):
            return HttpResponse("কার্টের তথ্য সঠিক নয়", status=400)
        if not quantities:
            return HttpResponse("কার্ট খালি", status=400)
        with transaction.atomic():
            items = list(MenuItem.objects.select_for_update().filter(
                id__in=quantities, restaurant=restaurant, is_available=True,
                category__restaurant=restaurant, category__is_active=True,
            ))
            if len(items) != len(quantities):
                return HttpResponse("এক বা একাধিক খাবার আর উপলব্ধ নেই", status=400)
            order = Order.objects.create(
                restaurant=restaurant, table=table,
                customer_name=name, customer_phone=phone,
            )
            total = Decimal("0.00")
            for item in items:
                qty = quantities[item.pk]
                OrderItem.objects.create(
                    order=order, menu_item=item, item_name=item.name,
                    unit_price=item.price, quantity=qty,
                )
                total += item.price * qty
            order.total = total
            order.save(update_fields=["total"])
        return redirect("track", slug=slug, token=order.public_token)
    categories = restaurant.categories.filter(is_active=True).prefetch_related("items")
    return render(request, "menu.html", {"restaurant": restaurant, "table": table, "categories": categories})

def track(request, slug, token):
    order = get_object_or_404(Order, restaurant__slug=slug, public_token=token)
    return render(request, "track.html", {"order": order})

@require_POST
def service(request, slug, number, kind):
    if kind not in ["waiter", "bill"]:
        raise Http404
    restaurant = get_object_or_404(Restaurant, slug=slug, is_active=True)
    table = get_object_or_404(DiningTable, restaurant=restaurant, number=number, is_active=True)
    ServiceRequest.objects.create(restaurant=restaurant, table=table, kind=kind)
    return redirect("menu", slug=slug, number=number)

def member(user, restaurant):
    return RestaurantMembership.objects.filter(user=user, restaurant=restaurant).first()

def require_role(user, restaurant, roles):
    membership = member(user, restaurant)
    return bool(user.is_staff or (membership and membership.role in roles))

@login_required
def dashboard(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, ["owner", "manager", "cashier"]):
        raise Http404
    from django.utils.timezone import localdate
    today = restaurant.orders.filter(created_at__date=localdate())
    sales = today.filter(status__in=["served", "paid"]).aggregate(v=Sum("total"))["v"] or 0
    return render(request, "dashboard.html", {
        "restaurant": restaurant, "orders": restaurant.orders.all()[:20],
        "count": today.count(), "sales": sales,
    })

@login_required
def kot(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, ["owner", "manager", "cashier", "kitchen"]):
        raise Http404
    orders = restaurant.orders.filter(
        status__in=["pending", "accepted", "preparing", "ready"]
    ).prefetch_related("items")
    return render(request, "kot.html", {"restaurant": restaurant, "orders": orders})

@login_required
@require_POST
def status(request, slug, pk):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    if not require_role(request.user, restaurant, ["owner", "manager", "cashier", "kitchen"]):
        raise Http404
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    flow = {
        "pending": ["accepted", "rejected"], "accepted": ["preparing"],
        "preparing": ["ready"], "ready": ["served"], "served": ["paid"],
    }
    new_status = request.POST.get("status")
    if new_status in flow.get(order.status, []):
        order.status = new_status
        order.save(update_fields=["status"])
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
        image = qrcode.make(f"{settings.SITE_URL}/r/{slug}/table/{table.number}/")
        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        image_buffer.seek(0)
        x = 45 + (index % 2) * 270
        y = 680 - ((index % 4) // 2) * 360
        pdf.drawImage(ImageReader(image_buffer), x, y, width=140, height=140)
        pdf.drawString(x, y - 20, f"{restaurant.name} - Table {table.number}")
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{slug}-qr.pdf"'
    return response
