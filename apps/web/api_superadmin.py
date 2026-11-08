from datetime import timedelta

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
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
        subs = Subscription.objects.select_related("restaurant", "plan")
        expiring = [s for s in subs if s.state == "expiring"]
        grace = [s for s in subs if s.state == "grace"]
        expired = [s for s in subs if s.state == "expired"]
        revenue = Payment.objects.filter(status__in=["paid", "approved"]).aggregate(t=Sum("amount"))["t"] or 0
        month = Payment.objects.filter(status__in=["paid", "approved"], paid_at__gte=now - timedelta(days=30)).aggregate(t=Sum("amount"))["t"] or 0
        return Response({
            "health": platform_health(),
            "restaurants": Restaurant.objects.count(),
            "pending": Restaurant.objects.filter(is_approved=False).count(),
            "blocked": Restaurant.objects.filter(is_blocked=True).count(),
            "active": sum(1 for s in subs if s.state in ("active", "expiring")),
            "expiring": [{"name": s.restaurant.name, "days_left": s.days_left, "end_date": s.end_date.isoformat()} for s in expiring],
            "grace": [{"name": s.restaurant.name, "end_date": s.end_date.isoformat()} for s in grace],
            "expired": [{"name": s.restaurant.name, "end_date": s.end_date.isoformat()} for s in expired],
            "revenue_total": str(revenue), "revenue_30d": str(month),
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
            Subscription.objects.create(restaurant=r, plan=plan, end_date=timezone.now() + timedelta(days=days))
        r.refresh_from_db()
        return Response(restaurant_admin_row(Restaurant.objects.select_related("subscription__plan").get(pk=pk)))


class ExtendView(ApproveView):
    """মেয়াদ বাড়ানো/প্ল্যান বদল (হাতে)। অনুমোদনের লজিক একই।"""


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


class PlanDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsPlatformAdmin]
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    http_method_names = ["get", "patch", "put", "delete"]

    def destroy(self, request, *args, **kwargs):
        plan = self.get_object()
        if plan.subscriptions.exists() or Payment.objects.filter(plan=plan).exists():
            return Response(
                {"detail": "এই প্ল্যানের সাবস্ক্রিপশন বা পেমেন্ট রেকর্ড আছে। মুছে না দিয়ে ‘বিক্রির জন্য চালু’ বন্ধ করুন।"},
                status=status.HTTP_409_CONFLICT,
            )
        plan.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PaymentListView(SuperBase):
    def get(self, request):
        qs = Payment.objects.select_related("restaurant", "plan")[:200]
        return Response([
            {"id": p.pk, "tran_id": p.tran_id, "restaurant": p.restaurant.name, "plan": p.plan.name,
             "amount": str(p.amount), "gateway": p.gateway, "method": p.method,
             "sender_number": p.sender_number, "trx_id": p.trx_id,
             "rejection_reason": p.rejection_reason, "status": p.status,
             "created_at": p.created_at.isoformat()} for p in qs
        ])



class ManualPaymentReviewView(SuperBase):
    @transaction.atomic
    def post(self, request, pk):
        payment = get_object_or_404(Payment.objects.select_for_update(), pk=pk, gateway="manual")
        if payment.status != Payment.Status.SUBMITTED:
            return Response({"detail": "এই পেমেন্ট আর পর্যালোচনার অপেক্ষায় নেই।"}, status=409)
        action = request.data.get("action")
        if action == "approve":
            payment.mark_paid("MANUAL-" + (payment.trx_id or ""), final_status=Payment.Status.APPROVED)
            payment.refresh_from_db()
            payment.reviewed_at = timezone.now()
            payment.save(update_fields=["reviewed_at"])
            return Response({"status": payment.status})
        if action == "reject":
            reason = str(request.data.get("reason", "")).strip()
            if not reason:
                return Response({"detail": "প্রত্যাখ্যানের কারণ লিখুন।"}, status=400)
            payment.status = Payment.Status.REJECTED
            payment.rejection_reason = reason[:500]
            payment.reviewed_at = timezone.now()
            payment.save(update_fields=["status", "rejection_reason", "reviewed_at"])
            return Response({"status": payment.status})
        return Response({"detail": "সঠিক সিদ্ধান্ত নির্বাচন করুন।"}, status=400)


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        r = ser.save()
        return Response({"ok": True, "slug": r.slug}, status=status.HTTP_201_CREATED)
