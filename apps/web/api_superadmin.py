from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsPlatformAdmin
from apps.payments.models import Payment
from apps.restaurants.models import Restaurant
from apps.subscriptions.models import Plan, Subscription

from .serializers import PlanSerializer, RegisterSerializer, restaurant_admin_row
from .throttles import RegisterThrottle


def platform_health():
    """ডেটাবেজ ও রিয়েল-টাইম লেয়ার সচল কি না (সুপার অ্যাডমিন হেলথ কার্ডের জন্য)।"""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    from django.db import connection

    health = {"database": True, "realtime": True, "checked_at": timezone.now().isoformat()}
    try:
        connection.ensure_connection()
    except Exception:
        health["database"] = False
    try:
        async_to_sync(get_channel_layer().group_send)("health_probe", {"type": "ping"})
    except Exception:
        health["realtime"] = False
    return health


class SuperBase(APIView):
    permission_classes = [IsPlatformAdmin]


class RestaurantListView(SuperBase):
    def get(self, request):
        qs = Restaurant.objects.select_related("subscription__plan").order_by("-created_at")
        return Response([restaurant_admin_row(r) for r in qs])


class StatsView(SuperBase):
    def get(self, request):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        subs = list(Subscription.objects.select_related("restaurant", "plan"))
        expiring = [s for s in subs if s.state == "expiring"]
        grace = [s for s in subs if s.state == "grace"]
        expired = [s for s in subs if s.state == "expired"]
        paid = Payment.objects.filter(status=Payment.Status.PAID)
        revenue = paid.aggregate(t=Sum("amount"))["t"] or 0
        month = paid.filter(paid_at__gte=month_start, paid_at__lt=now).aggregate(t=Sum("amount"))["t"] or 0
        last_30_days = paid.filter(paid_at__gte=now - timedelta(days=30)).aggregate(t=Sum("amount"))["t"] or 0
        return Response({
            "health": platform_health(),
            "restaurants": Restaurant.objects.count(),
            "pending": Restaurant.objects.filter(is_approved=False).count(),
            "blocked": Restaurant.objects.filter(is_blocked=True).count(),
            "active": sum(1 for s in subs if s.state in ("active", "expiring")),
            "expiring": [{"name": s.restaurant.name, "days_left": s.days_left, "end_date": s.end_date.isoformat()} for s in expiring],
            "grace": [{"name": s.restaurant.name, "end_date": s.end_date.isoformat()} for s in grace],
            "expired": [{"name": s.restaurant.name, "end_date": s.end_date.isoformat()} for s in expired],
            "revenue_total": str(revenue),
            "revenue_month": str(month),
            "revenue_30d": str(last_30_days),
        })


class ApproveView(SuperBase):
    @transaction.atomic
    def post(self, request, pk):
        r = get_object_or_404(Restaurant, pk=pk)
        plan = Plan.objects.filter(code=request.data.get("plan", "basic"), is_active=True).first()
        if not plan:
            return Response({"detail": "প্ল্যান পাওয়া যায়নি।"}, status=400)
        try:
            days = int(request.data.get("days") or plan.duration_days)
        except (TypeError, ValueError):
            return Response({"detail": "দিনের সংখ্যা সঠিক নয়।"}, status=400)
        if not 1 <= days <= 3650:
            return Response({"detail": "দিন ১ থেকে ৩৬৫০ এর মধ্যে দিন।"}, status=400)
        r.is_approved = True
        r.save(update_fields=["is_approved"])
        sub = r.current_subscription
        if sub:
            sub.extend(plan=plan, days=days)
        else:
            Subscription.objects.create(
                restaurant=r, plan=plan, end_date=timezone.now() + timedelta(days=days),
                grace_days=plan.grace_days,
            )
        return Response(restaurant_admin_row(Restaurant.objects.select_related("subscription__plan").get(pk=pk)))


class ExtendView(ApproveView):
    """মেয়াদ বাড়ানো/প্ল্যান বদল (হাতে)।"""


class TrialView(SuperBase):
    @transaction.atomic
    def post(self, request, pk):
        r = get_object_or_404(Restaurant, pk=pk)
        plan = Plan.objects.filter(code=request.data.get("plan", "basic"), is_active=True).first()
        if not plan:
            return Response({"detail": "সক্রিয় প্ল্যান নির্বাচন করুন।"}, status=400)
        try:
            days = int(request.data.get("days", 7))
        except (TypeError, ValueError):
            return Response({"detail": "ট্রায়ালের দিনের সংখ্যা সঠিক নয়।"}, status=400)
        if not 1 <= days <= 365:
            return Response({"detail": "ফ্রি ট্রায়াল ১ থেকে ৩৬৫ দিনের মধ্যে হতে হবে।"}, status=400)
        r.is_approved = True
        r.is_blocked = False
        r.save(update_fields=["is_approved", "is_blocked"])
        sub = r.current_subscription
        if sub:
            sub.extend(plan=plan, days=days)
        else:
            Subscription.objects.create(
                restaurant=r, plan=plan, end_date=timezone.now() + timedelta(days=days),
                grace_days=plan.grace_days,
            )
        return Response(restaurant_admin_row(Restaurant.objects.select_related("subscription__plan").get(pk=pk)))


class BlockView(SuperBase):
    block = True

    def post(self, request, pk):
        r = get_object_or_404(Restaurant, pk=pk)
        r.is_blocked = self.block
        r.save(update_fields=["is_blocked"])
        return Response(restaurant_admin_row(r))


class UnblockView(BlockView):
    block = False


class PlanListView(SuperBase):
    def get(self, request):
        return Response(PlanSerializer(Plan.objects.all(), many=True).data)

    def post(self, request):
        serializer = PlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.save()
        return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(generics.UpdateAPIView):
    permission_classes = [IsPlatformAdmin]
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    http_method_names = ["patch", "put"]


class PaymentListView(SuperBase):
    def get(self, request):
        qs = Payment.objects.select_related("restaurant", "plan")[:200]
        return Response([
            {"tran_id": p.tran_id, "restaurant": p.restaurant.name, "plan": p.plan.name,
             "amount": str(p.amount), "gateway": p.gateway, "status": p.status,
             "created_at": p.created_at.isoformat(),
             "paid_at": p.paid_at.isoformat() if p.paid_at else None}
            for p in qs
        ])


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        r = ser.save()
        return Response({"ok": True, "slug": r.slug}, status=status.HTTP_201_CREATED)
