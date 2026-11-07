"""সেলস রিপোর্ট। বিক্রি = পরিবেশিত (served) বা পরিশোধিত (paid) অর্ডার; বাতিল/চলমান ধরা হয় না।"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.utils import timezone

from apps.orders.models import Order, OrderItem, money

SOLD = ["served", "paid"]
PERIODS = {
    # নাম: (ট্রাঙ্কেট ফাংশন, কতটি বকেট)
    "daily": (TruncDay, 30),
    "weekly": (TruncWeek, 12),
    "monthly": (TruncMonth, 12),
}


def _start(period, now):
    local = timezone.localtime(now)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "daily":
        return midnight - timedelta(days=29)
    if period == "weekly":
        return midnight - timedelta(days=midnight.weekday()) - timedelta(weeks=11)
    first = midnight.replace(day=1)
    y, m = first.year, first.month - 11
    while m < 1:
        m += 12
        y -= 1
    return first.replace(year=y, month=m)


def _total(qs):
    agg = qs.aggregate(total=Sum("subtotal"), n=Count("id"))
    return {"total": str(money(agg["total"] or 0)), "orders": agg["n"]}


def sales_report(restaurant, period="daily"):
    if period not in PERIODS:
        period = "daily"
    trunc, _ = PERIODS[period]
    now = timezone.now()
    start = _start(period, now)
    qs = Order.objects.filter(restaurant=restaurant, status__in=SOLD, created_at__gte=start)

    rows = (
        qs.annotate(b=trunc("created_at"))
        .values("b")
        .annotate(total=Sum("subtotal"), n=Count("id"))
        .order_by("b")
    )
    series = [
        {"label": timezone.localtime(r["b"]).strftime("%Y-%m-%d" if period != "monthly" else "%Y-%m"),
         "total": float(r["total"] or 0), "orders": r["n"]}
        for r in rows
    ]

    local = timezone.localtime(now)
    today0 = local.replace(hour=0, minute=0, second=0, microsecond=0)
    base = Order.objects.filter(restaurant=restaurant, status__in=SOLD)
    summary = {
        "today": _total(base.filter(created_at__gte=today0)),
        "week": _total(base.filter(created_at__gte=today0 - timedelta(days=today0.weekday()))),
        "month": _total(base.filter(created_at__gte=today0.replace(day=1))),
    }

    top = (
        OrderItem.objects.filter(order__restaurant=restaurant, order__status__in=SOLD, order__created_at__gte=start)
        .values("name")
        .annotate(qty=Sum("quantity"))
        .order_by("-qty", "name")[:8]
    )
    top_items = []
    for t in top:
        revenue = sum(
            (i.unit_price * i.quantity for i in OrderItem.objects.filter(
                order__restaurant=restaurant, order__status__in=SOLD,
                order__created_at__gte=start, name=t["name"])),
            Decimal("0"),
        )
        top_items.append({"name": t["name"], "qty": t["qty"], "revenue": float(revenue)})

    return {"period": period, "series": series, "summary": summary, "top_items": top_items}
