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


class PulseView(TenantAPIView):
    """খুব হালকা পরিবর্তন-চেক (WebSocket ছাড়া হোস্টের জন্য): অর্ডার/সার্ভিস বদলালে 'v' বদলায়।"""
    permission_classes = [OrderStaffPermission]
    feature = "live_orders"

    def get(self, request):
        # অর্ডার কখনো ডিলিট হয় না এবং প্রতিটি পরিবর্তনে updated_at বদলায়, তাই শুধু Max(updated_at) যথেষ্ট;
        # (restaurant, updated_at) ইনডেক্সে এটি পুরো টেবিল স্ক্যান করে না।
        from django.db.models import Count, Max
        o = Order.objects.filter(restaurant=self.restaurant).aggregate(m=Max("updated_at"))
        sr = ServiceRequest.objects.filter(restaurant=self.restaurant, is_resolved=False).aggregate(n=Count("id"), m=Max("id"))
        return Response({"v": f"{o['m']}|{sr['n']}|{sr['m']}"})


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
class MenuCsvImportView(TenantAPIView):
    """Menu CSV import: name,category,price,description,is_veg → একবারে মেনু ভরা।

    পাশাপাশি CSV-তে থাকা নতুন ক্যাটাগরি নিজে থেকেই তৈরি হয়। পুরনো আইটেমের নাম+ক্যাটাগরি
    মিললে দাম/বিবরণ আপডেট হয় (ডুপ্লিকেট তৈরি হয় না)।
    """

    def post(self, request):
        import csv
        import io

        from apps.menu.constants import CSV_MAX_BYTES, CSV_MAX_ROWS
        from apps.menu.models import Category, MenuItem

        up = request.FILES.get("file")
        if not up:
            return Response({"detail": "CSV ফাইল দিন।"}, status=400)
        if up.size > CSV_MAX_BYTES:
            return Response({"detail": "ফাইলটি অনেক বড় (সর্বোচ্চ ৫১২ KB)।"}, status=400)
        try:
            text = up.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response({"detail": "ফাইলটি UTF-8 এ সংরক্ষণ করুন (Excel: CSV UTF-8)।"}, status=400)

        rows = list(csv.reader(io.StringIO(text)))
        if not rows:
            return Response({"detail": "ফাইলটি খালি।"}, status=400)
        header = [c.strip().lower() for c in rows[0]]
        need = {"name", "category", "price"}
        if not need.issubset(set(header)):
            return Response({"detail": "হেডারে অন্তত name, category, price কলাম লাগবে।"}, status=400)
        idx = {k: header.index(k) for k in header}
        if len(rows) - 1 > CSV_MAX_ROWS:
            return Response({"detail": f"একবারে সর্বোচ্চ {CSV_MAX_ROWS}টি লাইন ইমপোর্ট করা যায়।"}, status=400)

        created = updated = 0
        errors = []
        for n, raw in enumerate(rows[1:], start=2):
            if not any((c or "").strip() for c in raw):
                continue
            get = lambda col: (raw[idx[col]].strip() if col in idx and idx[col] < len(raw) else "")
            name, cat_name = get("name")[:120], get("category")[:80]
            if not name or not cat_name:
                errors.append(f"লাইন {n}: নাম ও ক্যাটাগরি লাগবে।")
                continue
            try:
                price = float(get("price").replace(",", ""))
            except ValueError:
                errors.append(f"লাইন {n}: দাম সংখ্যা নয়।")
                continue
            if price < 0 or price > 1_000_000:
                errors.append(f"লাইন {n}: দাম সীমার বাইরে।")
                continue
            cat, _ = Category.objects.get_or_create(restaurant=self.restaurant, name=cat_name)
            obj, is_new = MenuItem.objects.get_or_create(
                restaurant=self.restaurant, category=cat, name=name,
                defaults={"price": price, "description": get("description")[:300],
                          "is_veg": get("is_veg").lower() in ("1", "true", "yes", "veg", "y")},
            )
            if is_new:
                created += 1
            else:
                obj.price = price
                if "description" in idx:
                    obj.description = get("description")[:300]
                obj.save(update_fields=["price", "description"])
                updated += 1

        return Response({"created": created, "updated": updated, "errors": errors[:20],
                         "message": f"{created}টি নতুন, {updated}টি আপডেট হয়েছে।"})


class AnalyticsView(TenantAPIView):
    def get(self, request):
        return Response(sales_report(self.restaurant, request.query_params.get("period", "daily")))


class TableBoardView(TenantAPIView):
    """টেবিল বোর্ড: কোন টেবিল খালি, কোনটায় খোলা অর্ডার, কোনটায় বিল বাকি।

    একটিমাত্র কুয়েরিতে সব টেবিলের অবস্থা দেয় (নন-নেস্টেড aggregate), তাই টেবিল ২০০ হলেও হালকা।
    """

    def get(self, request):
        from django.db.models import Count, Q, Sum

        tables = list(Table.objects.filter(restaurant=self.restaurant, is_active=True).order_by("number"))
        rows = (
            Order.objects.filter(restaurant=self.restaurant)
            .exclude(status=Order.Status.REJECTED)
            .values("table_id")
            .annotate(
                active=Count("id", filter=Q(status__in=Order.ACTIVE_STATUSES)),
                served=Count("id", filter=Q(status=Order.Status.SERVED)),
                total=Sum("subtotal", filter=Q(status__in=["served", "paid"])),
            )
        )
        by_table = {r["table_id"]: r for r in rows}
        reqs = {r.table_id for r in ServiceRequest.objects.filter(restaurant=self.restaurant, is_resolved=False)}
        out = []
        for t in tables:
            r = by_table.get(t.pk) or {}
            active, served = r.get("active") or 0, r.get("served") or 0
            if active:
                state = "cooking"
            elif served:
                state = "bill"          # খাবার এসে গেছে, বিল বাকি
            else:
                state = "free"
            out.append({
                "id": t.pk, "number": t.number, "name": t.display_name,
                "state": state, "active": active, "served": served,
                "total": str(r.get("total") or 0), "waiting": t.pk in reqs,
            })
        summary = {
            "free": sum(1 for x in out if x["state"] == "free"),
            "cooking": sum(1 for x in out if x["state"] == "cooking"),
            "bill": sum(1 for x in out if x["state"] == "bill"),
            "waiting": sum(1 for x in out if x["waiting"]),
        }
        return Response({"tables": out, "summary": summary})


class OnboardingStatusView(TenantAPIView):
    """প্রথম লগইনে দেখানোর চেকলিস্ট। প্রতিটি ধাপ সত্যিকারের ডেটা থেকে যাচাই হয়।"""

    def get(self, request):
        r = self.restaurant
        sub = r.current_subscription
        has_table = Table.objects.filter(restaurant=r, is_active=True).exists()
        steps = [
            {"key": "menu", "label": "মেনুতে খাবার যোগ করুন", "url": "/merchant/menu/",
             "done": MenuItem.objects.filter(restaurant=r, is_active=True).exists()},
            {"key": "table", "label": "টেবিল তৈরি করে QR প্রিন্ট করুন", "url": "/merchant/tables/",
             "done": has_table},
            {"key": "branding", "label": "লোগো ও রং ঠিক করুন", "url": "/merchant/branding/",
             "done": bool(r.logo or r.cover_image) or r.theme != "light"},
            {"key": "subscription", "label": "সাবস্ক্রিপশন চালু রাখুন", "url": "/merchant/billing/",
             "done": bool(sub and sub.state in ("active", "expiring"))},
            {"key": "staff", "label": "স্টাফ অ্যাকাউন্ট তৈরি করুন", "url": "/merchant/staff/",
             "done": r.staff.exclude(role=User.Role.OWNER).exists()},
        ]
        return Response({
            "steps": steps,
            "done": all(s["done"] for s in steps),
            "completed": sum(1 for s in steps if s["done"]),
            "total": len(steps),
            "features": {k: r.has_feature(k) for k in ("live_orders", "qr_generator", "branding")},
            "approved": r.is_approved,
        })


class SalesCsvView(TenantAPIView):
    """বিক্রির CSV এক্সপোর্ট (পরিবেশিত/পরিশোধিত অর্ডার)। Excel-এ বাংলা ঠিক খুলতে UTF-8 BOM দেওয়া হয়।"""

    def get(self, request):
        import csv

        from django.http import HttpResponse
        from django.utils import timezone

        from apps.orders.models import Order

        qs = (
            Order.objects.filter(restaurant=self.restaurant, status__in=["served", "paid"])
            .select_related("table").prefetch_related("items").order_by("-created_at")
        )
        start = request.query_params.get("from")
        end = request.query_params.get("to")
        try:
            if start:
                qs = qs.filter(created_at__date__gte=start)
            if end:
                qs = qs.filter(created_at__date__lte=end)
        except Exception:
            return Response({"detail": "তারিখের ফরম্যাট সঠিক নয় (YYYY-MM-DD)।"}, status=400)

        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
        resp["Content-Disposition"] = f'attachment; filename="{self.restaurant.slug}-sales-{stamp}.csv"'
        resp.write("\ufeff")  # BOM
        w = csv.writer(resp)
        w.writerow(["তারিখ", "সময়", "অর্ডার", "টেবিল", "কাস্টমার", "মোবাইল", "খাবার", "পরিমাণ", "একক দাম", "লাইন মোট", "অর্ডার মোট", "অবস্থা"])
        for o in qs:
            local = timezone.localtime(o.created_at)
            base = [local.strftime("%Y-%m-%d"), local.strftime("%H:%M"), o.pk,
                    o.table.display_name, o.customer_name, o.customer_phone]
            items = list(o.items.all())
            if not items:
                w.writerow(base + ["", "", "", "", o.subtotal, o.get_status_display()])
            for i in items:
                w.writerow(base + [i.name, i.quantity, i.unit_price, i.line_total, o.subtotal, o.get_status_display()])
        return resp


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
