"""পেমেন্ট গেটওয়ে: mock (ডেভ) ও SSLCommerz (বিকাশ/নগদ/রকেট সহ)।"""
import json
import urllib.parse
import urllib.request

from django.conf import settings
from django.urls import reverse


class GatewayError(Exception):
    pass


def _post(url, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _get(url, params):
    with urllib.request.urlopen(url + "?" + urllib.parse.urlencode(params), timeout=20) as resp:
        return json.loads(resp.read().decode())


class MockGateway:
    name = "mock"

    def initiate(self, payment, user):
        return reverse("payments:mock", args=[payment.tran_id])


class SSLCommerzGateway:
    name = "sslcommerz"

    @property
    def base(self):
        return "https://sandbox.sslcommerz.com" if settings.SSLCOMMERZ_SANDBOX else "https://securepay.sslcommerz.com"

    def initiate(self, payment, user):
        if not (settings.SSLCOMMERZ_STORE_ID and settings.SSLCOMMERZ_STORE_PASSWORD):
            raise GatewayError("SSLCommerz-এর স্টোর আইডি/পাসওয়ার্ড .env-এ সেট করা নেই।")
        site = settings.SITE_BASE_URL
        data = {
            "store_id": settings.SSLCOMMERZ_STORE_ID,
            "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD,
            "total_amount": str(payment.amount),
            "currency": "BDT",
            "tran_id": payment.tran_id,
            "success_url": site + reverse("payments:success"),
            "fail_url": site + reverse("payments:fail"),
            "cancel_url": site + reverse("payments:cancel"),
            "ipn_url": site + reverse("payments:ipn"),
            "cus_name": user.get_full_name() or user.username,
            "cus_email": user.email or "noreply@example.com",
            "cus_phone": user.phone or "01700000000",
            "cus_add1": payment.restaurant.address or "Bangladesh",
            "cus_city": "Dhaka",
            "cus_country": "Bangladesh",
            "shipping_method": "NO",
            "product_name": f"OrderMama {payment.plan.name}",
            "product_category": "Subscription",
            "product_profile": "non-physical-goods",
        }
        res = _post(self.base + "/gwprocess/v4/api.php", data)
        if res.get("status") != "SUCCESS" or not res.get("GatewayPageURL"):
            raise GatewayError(res.get("failedreason") or "গেটওয়ে সেশন তৈরি হয়নি।")
        return res["GatewayPageURL"]

    def validate(self, payment, val_id):
        """সার্ভার-সাইড যাচাই: নিজের টাকা-পরিমাণ ও tran_id মিলিয়ে দেখি।"""
        res = _get(
            self.base + "/validator/api/validationserverAPI.php",
            {
                "val_id": val_id,
                "store_id": settings.SSLCOMMERZ_STORE_ID,
                "store_passwd": settings.SSLCOMMERZ_STORE_PASSWORD,
                "format": "json",
            },
        )
        ok = (
            res.get("status") in ("VALID", "VALIDATED")
            and res.get("tran_id") == payment.tran_id
            and res.get("currency_type", "BDT") == "BDT"
            and abs(float(res.get("amount", 0)) - float(payment.amount)) < 0.01
        )
        return ok, res


def get_gateway():
    if settings.PAYMENT_GATEWAY == "sslcommerz":
        return SSLCommerzGateway()
    if settings.PAYMENT_GATEWAY == "mock":
        if not settings.DEBUG:
            raise GatewayError("প্রোডাকশনে mock গেটওয়ে চলবে না।")
        return MockGateway()
    raise GatewayError("অজানা পেমেন্ট গেটওয়ে।")
