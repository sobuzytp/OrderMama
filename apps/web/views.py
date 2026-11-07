"""HTML পেজ ভিউ। ডেটা JavaScript fetch দিয়ে আসে; এখানে শুধু কাঠামো, ব্র্যান্ডিং ও অ্যাক্সেস-নিয়ন্ত্রণ।"""
import json
from functools import wraps

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.accounts.models import User
from apps.payments.models import Payment
from apps.realtime.tokens import make_table_token
from apps.restaurants.models import Restaurant, Table
from apps.subscriptions.models import Plan

from .utils import brand_for

R = User.Role

# মেনুর আইটেম অনুযায়ী ন্যাভ: (ইউআরএল-নাম, লেবেল, আইকন, অনুমোদিত রোল, ফিচার)
NAV = [
    ("dashboard:live", "লাইভ অর্ডার", "bell-ring", {R.OWNER, R.MANAGER, R.CASHIER, R.KITCHEN, R.WAITER}, "live_orders"),
    ("dashboard:bills", "টেবিল ও বিল", "receipt", {R.OWNER, R.MANAGER, R.CASHIER}, "live_orders"),
    ("dashboard:menu", "মেনু", "utensils", {R.OWNER, R.MANAGER}, None),
    ("dashboard:tables", "টেবিল ও QR", "qr-code", {R.OWNER, R.MANAGER}, None),
    ("dashboard:analytics", "বিক্রি", "chart-column", {R.OWNER, R.MANAGER}, None),
    ("dashboard:branding", "ব্র্যান্ডিং", "palette", {R.OWNER, R.MANAGER}, None),
    ("dashboard:staff", "স্টাফ", "users", {R.OWNER}, None),
    ("dashboard:billing", "সাবস্ক্রিপশন", "credit-card", {R.OWNER, R.MANAGER}, None),
]


def _lock_reason(r):
    if not r.is_approved:
        return "pending"
    if r.is_blocked:
        return "blocked"
    if not r.is_operational:
        return "expired"
    return ""


def staff_page(roles=None, feature=None, always=False):
    """ড্যাশবোর্ড পেজের গার্ড। always=True হলে মেয়াদ শেষেও খোলা (বিলিং পেজ)।"""

    def deco(view):
        @wraps(view)
        @login_required(login_url="/dashboard/login/")
        @ensure_csrf_cookie
        def wrapper(request, *a, **kw):
            u = request.user
            if u.is_superuser and not u.restaurant_id:
                return redirect("superadmin:home")
            if not u.restaurant_id:
                raise Http404
            r = u.restaurant
            ctx_lock = _lock_reason(r)
            if roles and u.role not in roles:
                return render(request, "dashboard/forbidden.html", _ctx(request, "প্রবেশাধিকার নেই"), status=403)
            if ctx_lock and not always:
                return render(request, "dashboard/locked.html", {**_ctx(request, ""), "lock": ctx_lock}, status=402)
            if feature and not r.has_feature(feature) and not ctx_lock:
                return render(request, "dashboard/upgrade.html", _ctx(request, ""), status=403)
            request.nav_active = request.resolver_match.view_name
            return view(request, *a, **kw)

        return wrapper

    return deco


def _ctx(request, title, **extra):
    u = request.user
    r = u.restaurant
    sub = r.current_subscription if r else None
    nav = [
        {"url": n[0], "label": n[1], "icon": n[2], "active": request.resolver_match.view_name == n[0]}
        for n in NAV if u.role in n[3]
    ]
    return {"title": title, "restaurant": r, "sub": sub, "nav": nav, "lock": _lock_reason(r) if r else "",
            "can_branding": r.has_feature("branding") if r else False, **extra}


class StaffLoginView(LoginView):
    template_name = "dashboard/login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        u = self.request.user
        if u.is_superuser and not u.restaurant_id:
            return "/superadmin/"
        return self.get_redirect_url() or "/dashboard/"


@login_required(login_url="/dashboard/login/")
def dashboard_home(request):
    u = request.user
    if u.is_superuser and not u.restaurant_id:
        return redirect("superadmin:home")
    r = u.restaurant
    if r and r.is_operational and r.has_feature("live_orders"):
        return redirect("dashboard:live")
    return redirect("dashboard:menu" if u.role in (R.OWNER, R.MANAGER) else "dashboard:live")


@staff_page(feature="live_orders")
def live(request):
    return render(request, "dashboard/live.html", _ctx(request, "লাইভ অর্ডার"))


@staff_page(roles={R.OWNER, R.MANAGER, R.CASHIER}, feature="live_orders")
def bills(request):
    return render(request, "dashboard/bills.html", _ctx(request, "টেবিল ও বিল"))


@staff_page(roles={R.OWNER, R.MANAGER})
def menu_manage(request):
    return render(request, "dashboard/menu.html", _ctx(request, "মেনু ম্যানেজমেন্ট"))


@staff_page(roles={R.OWNER, R.MANAGER})
def tables(request):
    r = request.user.restaurant
    return render(request, "dashboard/tables.html",
                  _ctx(request, "টেবিল ও QR", can_qr=r.has_feature("qr_generator"), site_url=settings.SITE_BASE_URL))


@staff_page(roles={R.OWNER, R.MANAGER})
def analytics(request):
    return render(request, "dashboard/analytics.html", _ctx(request, "সেলস অ্যানালিটিক্স"))


@staff_page(roles={R.OWNER, R.MANAGER}, feature="branding")
def branding(request):
    return render(request, "dashboard/branding.html", _ctx(request, "ব্র্যান্ডিং সেটিংস"))


@staff_page(roles={R.OWNER})
def staff(request):
    return render(request, "dashboard/staff.html", _ctx(request, "স্টাফ"))


@staff_page(roles={R.OWNER, R.MANAGER}, always=True)
def billing(request):
    r = request.user.restaurant
    return render(request, "dashboard/billing.html", _ctx(
        request, "সাবস্ক্রিপশন",
        plans=Plan.objects.filter(is_active=True),
        payments=Payment.objects.filter(restaurant=r)[:15],
    ))


# ---------- কাস্টমার ----------
def customer_menu(request, slug, number=None):
    r = get_object_or_404(Restaurant, slug=slug)
    if not r.is_operational:
        return render(request, "customer/unavailable.html", {"restaurant": r}, status=403)
    table = None
    token = ""
    if number is not None:
        table = get_object_or_404(Table, restaurant=r, number=number, is_active=True)
        token = make_table_token(table)
    brand = brand_for(r)
    boot = {
        "slug": r.slug, "table": table.number if table else None, "token": token,
        "restaurantName": r.name,
        "api": {"menu": f"/api/c/{r.slug}/menu/"},
    }
    if table:
        base = f"/api/c/{r.slug}/{table.number}"
        boot["api"].update(orders=f"{base}/orders/", waiter=f"{base}/call-waiter/",
                           bill=f"{base}/request-bill/", session=f"{base}/session/")
    resp = render(request, "customer/menu.html", {
        "restaurant": r, "table": table, "brand": brand, "boot": boot,
    })
    resp["Cache-Control"] = "no-store"
    return resp


def landing(request):
    return render(request, "customer/landing.html", {"plans": Plan.objects.filter(is_active=True)})


def register_page(request):
    return render(request, "customer/register.html")


def healthz(request):
    from django.http import JsonResponse
    return JsonResponse({"ok": True})
