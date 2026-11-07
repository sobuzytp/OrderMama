"""কাস্টমার API: লগইন ছাড়া, টেবিল-সেশন টোকেন ও রেট-লিমিট দিয়ে সুরক্ষিত।"""
from datetime import timedelta

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.menu.models import Category
from apps.orders.models import Bill, Order, ServiceRequest
from apps.orders.services import OrderError, call_waiter, order_payload, place_order, request_bill
from apps.realtime.tokens import make_table_token, read_table_token
from apps.restaurants.models import Restaurant, Table

from .serializers import OrderCreateSerializer
from .throttles import IpThrottle, TableSessionThrottle
from .utils import brand_for


class Unavailable(APIException):
    status_code = 403
    default_detail = "এই রেস্টুরেন্টের মেনু এখন চালু নেই।"
    default_code = "unavailable"


class PlanLimit(APIException):
    status_code = 403
    default_detail = "এই রেস্টুরেন্টে এখনো অনলাইন অর্ডার চালু নেই। ওয়েটারকে বলুন।"
    default_code = "ordering_disabled"


def public_restaurant(slug):
    r = get_object_or_404(Restaurant, slug=slug)
    if not r.is_operational:
        raise Unavailable()
    return r


def table_from_token(request, slug, number):
    """টোকেন যাচাই: স্বাক্ষর, মেয়াদ এবং URL-এর টেবিলের সাথে মিল।"""
    r = public_restaurant(slug)
    table = get_object_or_404(Table, restaurant=r, number=number, is_active=True)
    data = read_table_token(request.headers.get("X-Table-Session", ""))
    if not data or data["t"] != table.pk or data["r"] != r.pk:
        raise APIException_session()
    return r, table


def APIException_session():
    e = APIException("সেশনের মেয়াদ শেষ। পেজটি রিফ্রেশ করুন।")
    e.status_code = 401
    e.default_code = "session_expired"
    return e


class CustomerBase(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]


def menu_data(restaurant):
    cats = (
        Category.objects.filter(restaurant=restaurant, is_active=True)
        .prefetch_related("items")
    )
    out = []
    for c in cats:
        items = [
            {
                "id": i.pk, "name": i.name, "description": i.description, "price": str(i.price),
                "image": i.image.url if i.image else "", "is_veg": i.is_veg,
                "is_stock_out": i.is_stock_out,
            }
            for i in c.items.all() if i.is_active
        ]
        if items:
            out.append({"id": c.pk, "name": c.name, "items": items})
    return out


class MenuView(CustomerBase):
    def get(self, request, slug):
        r = public_restaurant(slug)
        return Response(
            {
                "restaurant": {"name": r.name, "slug": r.slug, "phone": r.phone, **brand_for(r)},
                "ordering_enabled": r.has_feature("live_orders"),
                "vat_percent": str(r.vat_percent),
                "service_charge_percent": str(r.service_charge_percent),
                "categories": menu_data(r),
            }
        )


class SessionView(CustomerBase):
    """টোকেন নবায়ন (পেজ অনেকক্ষণ খোলা থাকলে)।"""

    throttle_classes = [TableSessionThrottle, IpThrottle]
    throttle_scope = "customer_session"

    def post(self, request, slug, number):
        r = public_restaurant(slug)
        table = get_object_or_404(Table, restaurant=r, number=number, is_active=True)
        return Response({"token": make_table_token(table)})


class OrdersView(CustomerBase):
    throttle_classes = [TableSessionThrottle, IpThrottle]
    throttle_scope = "customer_order"

    def get_throttles(self):
        # শুধু অর্ডার সাবমিটে কড়া লিমিট; তালিকা দেখায় ঢিলা
        if self.request.method == "GET":
            self.throttle_scope = "customer_session"
        return super().get_throttles()

    def get(self, request, slug, number):
        r, table = table_from_token(request, slug, number)
        bill = Bill.objects.filter(table=table).exclude(status=Bill.Status.PAID).first()
        if not bill:
            return Response({"bill": None, "orders": []})
        orders = bill.orders.select_related("table").prefetch_related("items").order_by("created_at")
        data = []
        for o in orders:
            d = order_payload(o)
            d.pop("customer_phone", None)
            data.append(d)
        return Response({"bill": {"id": bill.pk, "status": bill.status, **{k: str(v) for k, v in bill.totals().items()}},
                         "orders": data})

    def post(self, request, slug, number):
        r, table = table_from_token(request, slug, number)
        if not r.has_feature("live_orders"):
            raise PlanLimit()
        ser = OrderCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        try:
            order = place_order(
                restaurant=r, table=table, customer_name=v["customer_name"],
                customer_phone=v["customer_phone"], items=v["items"], note=v["note"],
            )
        except OrderError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        d = order_payload(order)
        d.pop("customer_phone", None)
        return Response(d, status=status.HTTP_201_CREATED)


def _recent_request(table, kind):
    return ServiceRequest.objects.filter(
        table=table, kind=kind, is_resolved=False,
        created_at__gte=timezone.now() - timedelta(minutes=2),
    ).first()


class CallWaiterView(CustomerBase):
    throttle_classes = [TableSessionThrottle, IpThrottle]
    throttle_scope = "customer_call"

    def post(self, request, slug, number):
        r, table = table_from_token(request, slug, number)
        if not r.has_feature("live_orders"):
            raise PlanLimit()
        if not _recent_request(table, "waiter"):
            call_waiter(table)
        return Response({"ok": True, "detail": "ওয়েটারকে জানানো হয়েছে।"})


class RequestBillView(CustomerBase):
    throttle_classes = [TableSessionThrottle, IpThrottle]
    throttle_scope = "customer_call"

    def post(self, request, slug, number):
        r, table = table_from_token(request, slug, number)
        if not r.has_feature("live_orders"):
            raise PlanLimit()
        try:
            if not _recent_request(table, "bill"):
                request_bill(table)
        except OrderError as e:
            return Response({"detail": str(e)}, status=400)
        return Response({"ok": True, "detail": "বিলের অনুরোধ পাঠানো হয়েছে।"})
