import uuid
from datetime import timedelta

from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth.middleware import get_user  # noqa: F401
from django.core.cache import cache
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.menu.models import Category, MenuItem
from apps.orders.models import Bill, Order
from apps.payments.models import Payment
from apps.realtime.routing import websocket_urlpatterns
from apps.realtime.tokens import make_table_token
from apps.restaurants.models import Restaurant, Table
from apps.subscriptions.models import Plan, Subscription

R = User.Role


def make_plans():
    basic = Plan.objects.create(code="basic", name="বেসিক", price=499)
    prem = Plan.objects.create(code="premium", name="প্রিমিয়াম", price=1499,
                               live_orders=True, qr_generator=True, branding=True)
    return basic, prem


def make_restaurant(slug="cafe-a", plan=None, days=30, approved=True):
    r = Restaurant.objects.create(name=f"Cafe {slug}", slug=slug, is_approved=approved,
                                  vat_percent=5, service_charge_percent=10)
    if plan:
        Subscription.objects.create(restaurant=r, plan=plan, end_date=timezone.now() + timedelta(days=days))
    cat = Category.objects.create(restaurant=r, name="মেইন")
    a = MenuItem.objects.create(restaurant=r, category=cat, name="বিরিয়ানি", price=250, is_veg=False)
    b = MenuItem.objects.create(restaurant=r, category=cat, name="সালাদ", price=100, is_veg=True)
    t = Table.objects.create(restaurant=r, number=5)
    return r, t, a, b


def staff(r, role, name=None):
    return User.objects.create_user(username=name or f"{r.slug}-{role}", password="Pass-12345!", restaurant=r, role=role)


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.basic, self.prem = make_plans()
        self.r, self.t, self.a, self.b = make_restaurant(plan=self.prem)
        self.c = Client()

    def hdr(self, table=None):
        return {"HTTP_X_TABLE_SESSION": make_table_token(table or self.t)}

    def order(self, items=None, **kw):
        body = {"customer_name": "রহিম", "customer_phone": "01712345678",
                "items": items if items is not None else [{"id": self.a.pk, "qty": 2, "note": "কম ঝাল"}]}
        body.update(kw)
        return self.c.post(f"/api/c/{self.r.slug}/t/{self.t.token}/orders/", body, content_type="application/json", **self.hdr())

    def login(self, user):
        c = Client()
        assert c.login(username=user.username, password="Pass-12345!")
        return c


class CustomerFlowTests(Base):
    def test_page_menu_and_table_detection(self):
        res = self.c.get(f"/cafe-a/{self.t.token}/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "--primary")
        self.assertEqual(self.c.get(f"/cafe-a/{uuid.uuid4()}/").status_code, 404)
        menu = self.c.get("/api/c/cafe-a/menu/").json()
        self.assertTrue(menu["ordering_enabled"])
        self.assertEqual(menu["categories"][0]["items"][0]["name"], "বিরিয়ানি")

    def test_price_comes_from_db_and_bill_is_shared(self):
        res = self.order()
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()["subtotal"], "500.00")
        self.assertNotIn("customer_phone", res.json())
        self.order(customer_name="করিম", items=[{"id": self.b.pk, "qty": 1}])
        self.assertEqual(Bill.objects.count(), 1)  # একই টেবিল = এক বিল
        self.assertEqual(Order.objects.count(), 2)
        listing = self.c.get(f"/api/c/cafe-a/t/{self.t.token}/orders/", **self.hdr()).json()
        self.assertEqual(len(listing["orders"]), 2)
        self.assertEqual(listing["bill"]["subtotal"], "600.00")
        self.assertEqual(listing["bill"]["total"], "690.00")  # ৫% ভ্যাট + ১০% সার্ভিস

    def test_validation_and_security(self):
        self.assertEqual(self.order(customer_phone="123").status_code, 400)
        self.assertEqual(self.order(items=[]).status_code, 400)
        self.assertEqual(self.order(items=[{"id": self.a.pk, "qty": 0}]).status_code, 400)
        self.assertEqual(self.order(items=[{"id": 99999, "qty": 1}]).status_code, 400)
        # টোকেন ছাড়া / ভুল টেবিলের টোকেন
        res = self.c.post(f"/api/c/cafe-a/t/{self.t.token}/orders/", {"customer_name": "x"}, content_type="application/json")
        self.assertEqual(res.status_code, 401)
        t2 = Table.objects.create(restaurant=self.r, number=6)
        res = self.c.post(f"/api/c/cafe-a/t/{self.t.token}/orders/", {}, content_type="application/json", **self.hdr(t2))
        self.assertEqual(res.status_code, 401)

    def test_table_token_unguessable_and_discount_badge(self):
        self.assertEqual(self.c.get("/cafe-a/table-5/").status_code, 404)  # নম্বর-লিংক আর চলে না
        self.a.compare_at_price = 300
        self.a.save()
        item = self.c.get("/api/c/cafe-a/menu/").json()["categories"][0]["items"][0]
        self.assertEqual(item["discount_percent"], 16)

    def test_stock_out_blocks_order(self):
        self.a.is_stock_out = True
        self.a.save()
        res = self.order()
        self.assertEqual(res.status_code, 400)
        self.assertIn("স্টকে নেই", res.json()["detail"])

    def test_cross_tenant_item_rejected(self):
        r2, t2, a2, _ = make_restaurant("cafe-b", self.prem)
        res = self.order(items=[{"id": a2.pk, "qty": 1}])
        self.assertEqual(res.status_code, 400)

    def test_rate_limit(self):
        codes = [self.order().status_code for _ in range(12)]
        self.assertIn(429, codes)
        self.assertEqual(codes.count(201), 10)

    def test_waiter_and_bill_request(self):
        res = self.c.post(f"/api/c/cafe-a/t/{self.t.token}/call-waiter/", {}, content_type="application/json", **self.hdr())
        self.assertEqual(res.status_code, 200)
        res = self.c.post(f"/api/c/cafe-a/t/{self.t.token}/request-bill/", {}, content_type="application/json", **self.hdr())
        self.assertEqual(res.status_code, 400)  # অর্ডার নেই
        self.order()
        res = self.c.post(f"/api/c/cafe-a/t/{self.t.token}/request-bill/", {}, content_type="application/json", **self.hdr())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Bill.objects.get().status, "requested")


class SubscriptionTests(Base):
    def test_basic_plan_is_menu_only(self):
        r, t, a, _ = make_restaurant("cafe-basic", self.basic)
        self.assertFalse(self.c.get("/api/c/cafe-basic/menu/").json()["ordering_enabled"])
        res = self.c.post(f"/api/c/cafe-basic/t/{t.token}/orders/", {}, content_type="application/json",
                          HTTP_X_TABLE_SESSION=make_table_token(t))
        self.assertEqual(res.status_code, 403)

    def test_grace_period_then_shutdown(self):
        sub = self.r.subscription
        sub.end_date = timezone.now() - timedelta(days=1)
        sub.save()
        self.assertEqual(sub.state, "grace")
        self.assertEqual(self.c.get("/api/c/cafe-a/menu/").status_code, 200)  # গ্রেসে এখনো চালু
        sub.end_date = timezone.now() - timedelta(days=5)
        sub.save()
        self.assertEqual(self.c.get("/api/c/cafe-a/menu/").status_code, 403)
        self.assertEqual(self.c.get(f"/cafe-a/{self.t.token}/").status_code, 403)

    def test_payment_reactivates_and_is_idempotent(self):
        sub = self.r.subscription
        sub.end_date = timezone.now() - timedelta(days=9)
        sub.save()
        self.assertEqual(self.c.get("/api/c/cafe-a/menu/").status_code, 403)
        p = Payment.objects.create(restaurant=self.r, plan=self.prem, amount=self.prem.price, gateway="mock")
        p.mark_paid("X1")
        p.mark_paid("X1")
        sub.refresh_from_db()
        self.assertGreater(sub.end_date, timezone.now() + timedelta(days=29))
        self.assertLess(sub.end_date, timezone.now() + timedelta(days=31)) 
        self.assertEqual(self.c.get("/api/c/cafe-a/menu/").status_code, 200)

    def test_blocked_and_unapproved(self):
        self.r.is_blocked = True
        self.r.save()
        self.assertEqual(self.c.get("/api/c/cafe-a/menu/").status_code, 403)


class DashboardTests(Base):
    def setUp(self):
        super().setUp()
        self.owner = staff(self.r, R.OWNER)
        self.kitchen = staff(self.r, R.KITCHEN)
        self.cashier = staff(self.r, R.CASHIER)
        self.order_id = self.order().json()["id"]

    def post_status(self, client, status, oid=None, **kw):
        return client.post(f"/api/d/orders/{oid or self.order_id}/status/", {"status": status, **kw},
                           content_type="application/json")

    def test_status_flow_and_roles(self):
        kc, cc, oc = self.login(self.kitchen), self.login(self.cashier), self.login(self.owner)
        self.assertEqual(self.post_status(kc, "accepted").status_code, 403)  # কিচেন অ্যাকসেপ্ট করতে পারে না
        self.assertEqual(self.post_status(cc, "accepted").status_code, 200)
        self.assertEqual(self.post_status(cc, "ready").status_code, 403)
        self.assertEqual(self.post_status(kc, "ready").status_code, 400)  # preparing বাদ দিয়ে লাফ
        self.assertEqual(self.post_status(kc, "preparing").status_code, 200)
        self.assertEqual(self.post_status(kc, "ready").status_code, 200)
        self.assertEqual(self.post_status(cc, "served").status_code, 200)
        track = self.c.get(f"/api/c/cafe-a/t/{self.t.token}/orders/", **self.hdr()).json()
        self.assertEqual(track["orders"][0]["status"], "served")
        self.assertEqual(self.post_status(oc, "bogus").status_code, 400)

    def test_reject_with_reason(self):
        cc = self.login(self.cashier)
        res = self.post_status(cc, "rejected", reason="আইটেম শেষ")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Order.objects.get().reject_reason, "আইটেম শেষ")
        self.assertEqual(self.post_status(cc, "accepted").status_code, 400)

    def test_tenant_isolation(self):
        r2, *_ = make_restaurant("cafe-b", self.prem)
        other = self.login(staff(r2, R.OWNER))
        self.assertEqual(self.post_status(other, "accepted").status_code, 403)  # ID অনুমান → 403
        self.assertEqual(other.get("/api/d/orders/").json(), [])
        self.assertEqual(other.get("/api/d/menu-items/").json()[0]["name"], "বিরিয়ানি")  # নিজের মেনু
        self.assertEqual(len(other.get("/api/d/menu-items/").json()), 2)

    def test_id_guessing_returns_403_everywhere(self):
        r2, t2, a2, _ = make_restaurant("cafe-b", self.prem)
        other = self.login(staff(r2, R.OWNER))
        mine = MenuItem.objects.get(pk=self.a.pk)
        self.assertEqual(other.patch(f"/api/d/menu-items/{mine.pk}/", {"price": "1"}, content_type="application/json").status_code, 403)
        self.assertEqual(other.delete(f"/api/d/menu-items/{mine.pk}/").status_code, 403)
        self.assertEqual(other.patch(f"/api/d/categories/{mine.category_id}/", {"name": "x"}, content_type="application/json").status_code, 403)
        self.assertEqual(other.patch(f"/api/d/tables/{self.t.pk}/", {"label": "x"}, content_type="application/json").status_code, 403)
        self.assertEqual(other.get(f"/api/d/qr/?table={self.t.pk}").status_code, 403)
        bill = Bill.objects.get()
        self.assertEqual(other.post(f"/api/d/bills/{bill.pk}/pay/", {}, content_type="application/json").status_code, 403)
        self.assertEqual(MenuItem.objects.get(pk=mine.pk).price, self.a.price)  # কিছুই বদলায়নি
        self.assertEqual(other.patch("/api/d/menu-items/999999/", {}, content_type="application/json").status_code, 404)

    def test_kitchen_cannot_see_analytics_or_menu(self):
        kc = self.login(self.kitchen)
        self.assertEqual(kc.get("/api/d/analytics/").status_code, 403)
        self.assertEqual(kc.get("/api/d/menu-items/").status_code, 403)
        self.assertEqual(kc.get("/merchant/analytics/").status_code, 403)
        self.assertEqual(kc.get("/api/d/orders/").status_code, 200)
        self.assertEqual(kc.get("/merchant/live/").status_code, 200)

    def test_unauthenticated(self):
        self.assertIn(self.c.get("/api/d/orders/").status_code, (401, 403))
        self.assertEqual(self.c.get("/merchant/live/").status_code, 302)

    def test_bill_pay_requires_all_served(self):
        cc = self.login(self.cashier)
        bill = Bill.objects.get()
        self.assertEqual(cc.post(f"/api/d/bills/{bill.pk}/pay/", {}, content_type="application/json").status_code, 409)
        for s in ["accepted", "preparing", "ready", "served"]:
            self.post_status(self.login(self.owner), s)
        res = cc.post(f"/api/d/bills/{bill.pk}/pay/", {}, content_type="application/json")
        self.assertEqual(res.status_code, 200)
        bill.refresh_from_db()
        self.assertEqual(bill.status, "paid")
        self.assertEqual(Order.objects.get().status, "paid")
        # পরের অর্ডারে নতুন বিল খোলে
        self.order()
        self.assertEqual(Bill.objects.count(), 2)

    def test_menu_crud_and_stock_toggle(self):
        oc = self.login(self.owner)
        cat = Category.objects.get()
        res = oc.post("/api/d/menu-items/", {"category": cat.pk, "name": "চা", "price": "20"})
        self.assertEqual(res.status_code, 201, res.content)
        iid = res.json()["id"]
        res = oc.patch(f"/api/d/menu-items/{iid}/", {"is_stock_out": True}, content_type="application/json")
        self.assertTrue(res.json()["is_stock_out"])
        # অন্য রেস্টুরেন্টের ক্যাটাগরি দেওয়া যাবে না
        r2, *_ = make_restaurant("cafe-b", self.prem)
        c2 = Category.objects.filter(restaurant=r2).first()
        res = oc.post("/api/d/menu-items/", {"category": c2.pk, "name": "x", "price": "1"})
        self.assertEqual(res.status_code, 400)

    def test_image_upload_compressed_and_validated(self):
        import io
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        oc = self.login(self.owner)
        buf = io.BytesIO()
        Image.new("RGB", (3000, 2000), "red").save(buf, "PNG")
        f = SimpleUploadedFile("big.png", buf.getvalue(), "image/png")
        res = oc.post("/api/d/menu-items/", {"category": Category.objects.get().pk, "name": "ছবি", "price": "5", "image": f})
        self.assertEqual(res.status_code, 201, res.content)
        item = MenuItem.objects.get(name="ছবি")
        self.assertTrue(item.image.name.endswith(".webp"))
        self.assertLessEqual(max(Image.open(item.image.path).size), 1200)
        item.image.delete()
        bad = SimpleUploadedFile("x.png", b"not an image", "image/png")
        res = oc.post("/api/d/menu-items/", {"category": Category.objects.get().pk, "name": "bad", "price": "5", "image": bad})
        self.assertEqual(res.status_code, 400)

    def test_tables_generate_and_qr_pdf(self):
        oc = self.login(self.owner)
        res = oc.post("/api/d/tables/generate/", {"count": 4}, content_type="application/json")
        self.assertEqual(res.json()["created"], 4)  # ১-৪ নেই, ৫ আগেই আছে
        pdf = oc.get("/api/d/qr/")
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        self.assertEqual(oc.post("/api/d/tables/generate/", {"count": 0}, content_type="application/json").status_code, 400)

    def test_qr_blocked_on_basic_plan(self):
        r, *_ = make_restaurant("cafe-basic", self.basic)
        res = self.login(staff(r, R.OWNER)).get("/api/d/qr/")
        self.assertEqual(res.status_code, 403)

    def test_branding_and_customer_theme(self):
        oc = self.login(self.owner)
        res = oc.patch("/api/d/branding/", {"primary_color": "#112233", "theme": "dark"}, content_type="application/json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertContains(self.c.get(f"/cafe-a/{self.t.token}/"), "#112233")
        self.assertEqual(oc.patch("/api/d/branding/", {"primary_color": "red"}, content_type="application/json").status_code, 400)

    def test_analytics(self):
        oc = self.login(self.owner)
        for s in ["accepted", "preparing", "ready", "served"]:
            self.post_status(oc, s)
        data = oc.get("/api/d/analytics/?period=daily").json()
        self.assertEqual(data["summary"]["today"]["total"], "500.00")
        self.assertEqual(data["top_items"][0], {"name": "বিরিয়ানি", "qty": 2, "revenue": 500.0})
        for p in ("weekly", "monthly"):
            self.assertEqual(oc.get(f"/api/d/analytics/?period={p}").status_code, 200)

    def test_staff_management_owner_only(self):
        oc = self.login(self.owner)
        res = oc.post("/api/d/staff/", {"username": "w1", "password": "Waiter-9988", "role": "waiter"})
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(User.objects.get(username="w1").restaurant, self.r)
        self.assertEqual(oc.post("/api/d/staff/", {"username": "o2", "password": "Waiter-9988", "role": "owner"}).status_code, 400)
        mgr = staff(self.r, R.MANAGER)
        self.assertEqual(self.login(mgr).get("/api/d/staff/").status_code, 403)


class SuperAdminTests(Base):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser("root", password="Pass-12345!")
        self.ac = self.login(self.admin)

    def test_register_approve_block(self):
        res = self.c.post("/api/register/", {"restaurant_name": "নতুন", "slug": "nutun", "phone": "01712345678",
                                             "username": "nutun-owner", "password": "Strong-pass-77"},
                          content_type="application/json")
        self.assertEqual(res.status_code, 201, res.content)
        r = Restaurant.objects.get(slug="nutun")
        self.assertFalse(r.is_approved)
        self.assertEqual(self.c.get("/api/c/nutun/menu/").status_code, 403)  # অনুমোদনের আগে বন্ধ
        res = self.ac.post(f"/api/sa/restaurants/{r.pk}/approve/", {"plan": "premium", "days": 30}, content_type="application/json")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(self.c.get("/api/c/nutun/menu/").status_code, 200)
        self.ac.post(f"/api/sa/restaurants/{r.pk}/block/", {}, content_type="application/json")
        self.assertEqual(self.c.get("/api/c/nutun/menu/").status_code, 403)
        self.ac.post(f"/api/sa/restaurants/{r.pk}/unblock/", {}, content_type="application/json")
        self.assertEqual(self.c.get("/api/c/nutun/menu/").status_code, 200)

    def test_reserved_slug_and_duplicate(self):
        base = {"restaurant_name": "x", "phone": "01712345678", "username": "u1", "password": "Strong-pass-77"}
        for slug in ("dashboard", "merchant", "super-admin", "cafe-a"):
            res = self.c.post("/api/register/", {**base, "slug": slug}, content_type="application/json")
            self.assertEqual(res.status_code, 400)

    def test_only_superuser(self):
        owner = self.login(staff(self.r, R.OWNER))
        self.assertEqual(owner.get("/api/sa/restaurants/").status_code, 403)
        self.assertEqual(owner.get("/super-admin/").status_code, 404)
        self.assertEqual(self.ac.get("/super-admin/").status_code, 200)
        stats = self.ac.get("/api/sa/stats/").json()
        self.assertEqual(stats["restaurants"], 1)
        self.assertTrue(stats["health"]["database"] and stats["health"]["realtime"])

    def test_expiry_warning_listing(self):
        sub = self.r.subscription
        sub.end_date = timezone.now() + timedelta(days=2)
        sub.save()
        self.assertEqual(self.ac.get("/api/sa/stats/").json()["expiring"][0]["name"], self.r.name)


@override_settings(DEBUG=True, PAYMENT_GATEWAY="mock")
class PaymentPageTests(Base):
    def test_mock_payment_flow(self):
        owner = staff(self.r, R.OWNER)
        oc = self.login(owner)
        sub = self.r.subscription
        sub.end_date = timezone.now() - timedelta(days=10)
        sub.save()
        self.assertEqual(oc.get("/merchant/live/").status_code, 402)  # মেয়াদ শেষ → লক
        self.assertEqual(oc.get("/merchant/billing/").status_code, 200)  # বিলিং খোলা
        res = oc.post("/payments/start/", {"plan": self.prem.pk})
        url = res.json()["redirect"]
        oc.post(url, {"result": "ok"})
        self.assertEqual(oc.get("/merchant/live/").status_code, 200)


class WebSocketTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        _, self.prem = make_plans()
        self.r, self.t, self.a, _ = make_restaurant(plan=self.prem)
        self.owner = staff(self.r, R.OWNER)
        self.kitchen = staff(self.r, R.KITCHEN)

    async def test_staff_gets_new_order_and_customer_gets_status(self):
        from channels.db import database_sync_to_async
        from apps.orders.services import change_status, place_order

        from urllib.parse import quote
        app = URLRouter(websocket_urlpatterns)
        # ব্রাউজার encodeURIComponent করে পাঠায় — ডিকোড না হলে আগে 403 আসত
        cust = WebsocketCommunicator(app, f"/ws/c/?token={quote(make_table_token(self.t), safe='')}")
        ok, _ = await cust.connect()
        self.assertTrue(ok)
        bad = WebsocketCommunicator(app, "/ws/c/?token=bogus")
        ok, _ = await bad.connect()
        self.assertFalse(ok)
        anon = WebsocketCommunicator(app, "/ws/dashboard/")
        anon.scope["user"] = __import__("django.contrib.auth.models", fromlist=["AnonymousUser"]).AnonymousUser()
        ok, _ = await anon.connect()
        self.assertFalse(ok)

        st = WebsocketCommunicator(app, "/ws/dashboard/")
        st.scope["user"] = self.owner
        ok, _ = await st.connect()
        self.assertTrue(ok)

        order = await database_sync_to_async(place_order)(
            restaurant=self.r, table=self.t, customer_name="রহিম", customer_phone="01712345678",
            items=[{"id": self.a.pk, "qty": 1}])
        ev = await st.receive_json_from(timeout=3)
        self.assertEqual(ev["type"], "order.new")
        self.assertEqual(ev["order"]["items"][0]["name"], "বিরিয়ানি")
        ev = await cust.receive_json_from(timeout=3)
        self.assertEqual(ev["type"], "order.update")
        self.assertNotIn("customer_phone", ev["order"])

        await database_sync_to_async(change_status)(order, "accepted")
        ev = await cust.receive_json_from(timeout=3)
        self.assertEqual(ev["order"]["status"], "accepted")

        # স্টক আউট → কাস্টমার মেনু-ইভেন্ট পায়
        def stock_out():
            self.a.is_stock_out = True
            self.a.save()
        await database_sync_to_async(stock_out)()
        ev = await cust.receive_json_from(timeout=3)
        self.assertEqual(ev["type"], "menu.change")
        for c in (cust, st):
            await c.disconnect()
