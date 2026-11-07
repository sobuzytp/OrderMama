"""রেস্টুরেন্ট স্টাফের API। প্রতিটি কোয়েরি request.user.restaurant দিয়ে ফিল্টার করা (মাল্টি-টেনান্সি)।"""
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import (
    STATUS_ROLES, BillingPermission, ManagerPermission, OrderStaffPermission, ServiceStaffPermission,
)
from apps.analytics.services import sales_report
from apps.menu.models import Category, MenuItem
from apps.orders.models import Bill, Order, ServiceRequest
from apps.orders.services import OrderError, change_status, order_payload
from apps.restaurants.models import Table

from .qr import build_qr_pdf
from .serializers import (
    BrandingSerializer, CategorySerializer, MenuItemSerializer, StaffSerializer, TableSerializer,
)


class SubscriptionRequired(APIException):
    status_code = 402
    default_code = "subscription"


class PlanRequired(APIException):
    status_code = 403
    default_code = "plan"


class TenantMixin:
    """সাবস্ক্রিপশন ও প্ল্যান-ফিচার গেট। feature: live_orders | qr_generator | branding"""

    feature = None
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @property
    def restaurant(self):
        return self.request.user.restaurant

    def check_permissions(self, request):
        super().check_permissions(request)
        r = request.user.restaurant
        if not r.is_approved:
            raise SubscriptionRequired("আপনার রেস্টুরেন্ট এখনো অনুমোদিত হয়নি।")
        if r.is_blocked:
            raise SubscriptionRequired("আপনার অ্যাকাউন্ট স্থগিত। সাপোর্টে যোগাযোগ করুন।")
        if not r.is_operational:
            raise SubscriptionRequired("সাবস্ক্রিপশনের মেয়াদ শেষ। রিনিউ করুন।")
        if self.feature and not r.has_feature(self.feature):
            raise PlanRequired("এই ফিচারটি আপনার বর্তমান প্ল্যানে নেই। প্রিমিয়ামে আপগ্রেড করুন।")


def owned_or_403(model, pk, restaurant):
    """ID অনুমান করে অন্য রেস্টুরেন্টের অবজেক্ট ধরতে গেলে সাথে সাথে 403 (নেই হলে 404)।"""
    obj = get_object_or_404(model.objects.all(), pk=pk)
    if obj.restaurant_id != restaurant.pk:
        raise PermissionDenied("এই তথ্যে আপনার অ্যাক্সেস নেই।")
    return obj


class TenantAPIView(TenantMixin, APIView):
    permission_classes = [ManagerPermission]


class TenantViewSet(TenantMixin, viewsets.ModelViewSet):
    permission_classes = [ManagerPermission]
    model = None  # সাবক্লাসে সেট হয়

    def get_object(self):
        obj = owned_or_403(self.model, self.kwargs["pk"], self.restaurant)
        obj = get_object_or_404(self.filter_queryset(self.get_queryset()), pk=obj.pk)
        self.check_object_permissions(self.request, obj)
        return obj

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["restaurant"] = self.restaurant
        return ctx


# ---------- লাইভ অর্ডার / KOT ----------
class OrderListView(TenantAPIView):
    permission_classes = [OrderStaffPermission]
    feature = "live_orders"

    def get(self, request):
        qs = (
            Order.objects.filter(restaurant=self.restaurant, status__in=[*Order.ACTIVE_STATUSES, "served"])
            .select_related("table").prefetch_related("items").order_by("created_at")
        )
        return Response([order_payload(o) for o in qs])


class OrderStatusView(TenantAPIView):
    permission_classes = [OrderStaffPermission]
    feature = "live_orders"

    def post(self, request, pk):
        order = owned_or_403(Order, pk, self.restaurant)
        new = request.data.get("status", "")
        if new not in STATUS_ROLES:
            return Response({"detail": "অবৈধ স্ট্যাটাস।"}, status=400)
        if request.user.role not in STATUS_ROLES[new]:
            raise PermissionDenied("এই কাজের অনুমতি আপনার রোলে নেই।")
        try:
            order = change_status(order, new, reason=str(request.data.get("reason", "")))
        except OrderError as e:
            return Response({"detail": str(e)}, status=400)
        order = Order.objects.select_related("table").prefetch_related("items").get(pk=order.pk)
        return Response(order_payload(order))


class ServiceRequestListView(TenantAPIView):
    permission_classes = [ServiceStaffPermission]
    feature = "live_orders"

    def get(self, request):
        qs = ServiceRequest.objects.filter(restaurant=self.restaurant, is_resolved=False).select_related("table")
        return Response([
            {"id": s.pk, "kind": s.kind, "kind_label": s.get_kind_display(), "table": s.table.number,
             "table_name": s.table.display_name, "created_at": s.created_at.isoformat()}
            for s in qs
        ])


class ServiceRequestResolveView(TenantAPIView):
    permission_classes = [ServiceStaffPermission]
    feature = "live_orders"

    def post(self, request, pk):
        s = owned_or_403(ServiceRequest, pk, self.restaurant)
        s.is_resolved = True
        s.save(update_fields=["is_resolved"])
        return Response({"ok": True})


# ---------- বিল ----------
def bill_payload(bill):
    return {
        "id": bill.pk, "table": bill.table.number, "table_name": bill.table.display_name,
        "status": bill.status, "opened_at": bill.opened_at.isoformat(),
        "totals": {k: str(v) for k, v in bill.totals().items()},
        "vat_percent": str(bill.restaurant.vat_percent),
        "service_charge_percent": str(bill.restaurant.service_charge_percent),
        "orders": [order_payload(o) for o in bill.orders.select_related("table").prefetch_related("items")
                   .exclude(status=Order.Status.REJECTED)],
        "all_served": not bill.orders.filter(status__in=Order.ACTIVE_STATUSES).exists(),
    }


class BillListView(TenantAPIView):
    permission_classes = [BillingPermission]
    feature = "live_orders"

    def get(self, request):
        qs = (Bill.objects.filter(restaurant=self.restaurant).exclude(status=Bill.Status.PAID)
              .select_related("table", "restaurant").order_by("opened_at"))
        return Response([bill_payload(b) for b in qs if b.orders.exclude(status="rejected").exists()])


class BillPayView(TenantAPIView):
    permission_classes = [BillingPermission]
    feature = "live_orders"

    def post(self, request, pk):
        bill = owned_or_403(Bill, pk, self.restaurant)
        if bill.status == Bill.Status.PAID:
            return Response({"detail": "বিলটি আগেই পরিশোধিত।"}, status=400)
        if bill.orders.filter(status__in=Order.ACTIVE_STATUSES).exists() and not (
            request.data.get("force") and request.user.is_restaurant_manager
        ):
            return Response({"detail": "এখনো কিছু অর্ডার পরিবেশিত হয়নি।", "code": "not_served"}, status=409)
        bill.mark_paid()
        return Response({"ok": True})


# ---------- মেনু ম্যানেজমেন্ট ----------
class CategoryViewSet(TenantViewSet):
    model = Category
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(restaurant=self.restaurant)

    def perform_create(self, serializer):
        serializer.save(restaurant=self.restaurant)


class MenuItemViewSet(TenantViewSet):
    model = MenuItem
    serializer_class = MenuItemSerializer
    pagination_class = None

    def get_queryset(self):
        return MenuItem.objects.filter(restaurant=self.restaurant).select_related("category")

    def perform_create(self, serializer):
        serializer.save(restaurant=self.restaurant)


# ---------- টেবিল ও QR ----------
class TableViewSet(TenantViewSet):
    model = Table
    serializer_class = TableSerializer
    pagination_class = None
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Table.objects.filter(restaurant=self.restaurant)

    def create(self, request, *args, **kwargs):
        """একটি নতুন টেবিল (পরবর্তী নম্বরে)।"""
        last = self.get_queryset().order_by("-number").first()
        t = Table.objects.create(restaurant=self.restaurant, number=(last.number + 1) if last else 1,
                                 label=str(request.data.get("label", ""))[:40])
        return Response(TableSerializer(t).data, status=201)

    def destroy(self, request, *args, **kwargs):
        t = self.get_object()
        if t.orders.exists():  # অর্ডার-ইতিহাস রাখতে নিষ্ক্রিয় করা হয়
            t.is_active = False
            t.save(update_fields=["is_active"])
            return Response({"deactivated": True})
        t.delete()
        return Response(status=204)

    @action(detail=False, methods=["post"])
    def generate(self, request):
        """টেবিল সংখ্যা দিলে ১..N পর্যন্ত নেই এমন টেবিলগুলো তৈরি হয়।"""
        try:
            count = int(request.data.get("count", 0))
        except (TypeError, ValueError):
            count = 0
        if not 1 <= count <= 200:
            return Response({"detail": "টেবিল সংখ্যা ১ থেকে ২০০ এর মধ্যে দিন।"}, status=400)
        have = set(self.get_queryset().values_list("number", flat=True))
        new = [Table(restaurant=self.restaurant, number=n) for n in range(1, count + 1) if n not in have]
        with transaction.atomic():
            Table.objects.bulk_create(new)
        # নতুন করে চালু করা (আগে নিষ্ক্রিয় থাকলে)
        self.get_queryset().filter(number__lte=count).update(is_active=True)
        return Response({"created": len(new), "tables": TableSerializer(self.get_queryset(), many=True).data})


class QRPdfView(TenantAPIView):
    feature = "qr_generator"

    def get(self, request):
        tables = Table.objects.filter(restaurant=self.restaurant, is_active=True)
        tid = request.query_params.get("table")
        if tid:
            if not str(tid).isdigit():
                return Response({"detail": "অবৈধ টেবিল।"}, status=400)
            owned_or_403(Table, int(tid), self.restaurant)
            tables = tables.filter(pk=tid)
        tables = list(tables)
        if not tables:
            return Response({"detail": "কোনো টেবিল নেই। আগে টেবিল তৈরি করুন।"}, status=404)
        pdf = build_qr_pdf(self.restaurant, tables)
        resp = HttpResponse(pdf, content_type="application/pdf")
        resp["Content-Disposition"] = f'inline; filename="{self.restaurant.slug}-qr.pdf"'
        return resp


# ---------- ব্র্যান্ডিং ----------
class BrandingView(TenantAPIView):
    feature = "branding"

    def get(self, request):
        return Response(BrandingSerializer(self.restaurant, context={"request": request}).data)

    def patch(self, request):
        ser = BrandingSerializer(self.restaurant, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


# ---------- অ্যানালিটিক্স ----------
class AnalyticsView(TenantAPIView):
    def get(self, request):
        return Response(sales_report(self.restaurant, request.query_params.get("period", "daily")))


# ---------- স্টাফ ----------
class StaffViewSet(TenantViewSet):
    model = User
    serializer_class = StaffSerializer
    pagination_class = None

    def check_permissions(self, request):
        super().check_permissions(request)
        if request.user.role != User.Role.OWNER:
            raise PermissionDenied("শুধু ওনার স্টাফ ম্যানেজ করতে পারবেন।")

    def get_queryset(self):
        return User.objects.filter(restaurant=self.restaurant).exclude(role=User.Role.OWNER)
