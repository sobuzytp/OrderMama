from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.subscriptions.models import Plan

from .gateways import GatewayError, SSLCommerzGateway, get_gateway
from .models import Payment


@login_required
@require_POST
def start_payment(request):
    user = request.user
    if not (user.restaurant_id and user.is_restaurant_manager):
        return JsonResponse({"detail": "অনুমতি নেই।"}, status=403)
    plan = get_object_or_404(Plan, pk=request.POST.get("plan"), is_active=True)
    payment = Payment.objects.create(
        restaurant=user.restaurant, plan=plan, amount=plan.price, gateway=settings.PAYMENT_GATEWAY
    )
    try:
        url = get_gateway().initiate(payment, user)
    except GatewayError as e:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
        return JsonResponse({"detail": str(e)}, status=502)
    return JsonResponse({"redirect": url})


@login_required
def mock_checkout(request, tran_id):
    """শুধু ডেভেলপমেন্টে: বিকাশ/নগদের নকল পেমেন্ট পেজ।"""
    if not settings.DEBUG or settings.PAYMENT_GATEWAY != "mock":
        raise Http404
    payment = get_object_or_404(Payment, tran_id=tran_id, restaurant=request.user.restaurant)
    if request.method == "POST":
        if request.POST.get("result") == "ok":
            payment.mark_paid("MOCK-" + tran_id)
        else:
            payment.status = Payment.Status.CANCELLED
            payment.save(update_fields=["status"])
        return redirect("/dashboard/billing/")
    html = (
        "<meta charset=utf-8><title>Mock Payment</title>"
        f"<h2>Mock পেমেন্ট — ৳{payment.amount} ({payment.plan.name})</h2>"
        "<form method=post>"
        f"<input type=hidden name=csrfmiddlewaretoken value='{get_token(request)}'>"
        "<button name=result value=ok>পেমেন্ট সফল</button> "
        "<button name=result value=cancel>বাতিল</button></form>"
    )
    return HttpResponse(html)


def _finish(request, ok_status):
    tran_id = request.POST.get("tran_id", "")
    payment = Payment.objects.filter(tran_id=tran_id).first()
    if not payment:
        return redirect("/dashboard/billing/")
    if ok_status == "paid":
        val_id = request.POST.get("val_id", "")
        try:
            ok, res = SSLCommerzGateway().validate(payment, val_id)
        except Exception:
            ok, res = False, {}
        if ok:
            payment.mark_paid(res.get("bank_tran_id") or val_id)
        elif payment.status == Payment.Status.PENDING:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status"])
    elif payment.status == Payment.Status.PENDING:
        payment.status = ok_status
        payment.save(update_fields=["status"])
    return redirect("/dashboard/billing/")


@csrf_exempt
@require_POST
def success(request):
    return _finish(request, "paid")


@csrf_exempt
@require_POST
def fail(request):
    return _finish(request, Payment.Status.FAILED)


@csrf_exempt
@require_POST
def cancel(request):
    return _finish(request, Payment.Status.CANCELLED)


@csrf_exempt
@require_POST
def ipn(request):
    _finish(request, "paid")
    return HttpResponse("OK")
