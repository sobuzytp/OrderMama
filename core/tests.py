import json
from django.contrib.auth import get_user_model
from django.test import TestCase
from .models import (
    Category, DiningTable, MenuItem, Order, Restaurant,
    RestaurantMembership, Subscription, Plan,
)

class OrderMamaTests(TestCase):
    def setUp(self):
        self.a = Restaurant.objects.create(name="Cafe A", slug="cafe-a")
        self.b = Restaurant.objects.create(name="Cafe B", slug="cafe-b")
        self.table = DiningTable.objects.create(restaurant=self.a, number=1)
        self.category = Category.objects.create(restaurant=self.a, name="Food")
        self.item = MenuItem.objects.create(
            restaurant=self.a, category=self.category, name="Rice", price="100.00"
        )
        self.user = get_user_model().objects.create_user(username="staff", password="test-pass-123")

    def test_public_menu_loads(self):
        self.assertEqual(self.client.get("/r/cafe-a/table/1/").status_code, 200)

    def test_menu_item_from_another_tenant_is_rejected(self):
        response = self.client.post(
            "/r/cafe-a/table/1/",
            {"name": "Test", "phone": "01700000000", "items": json.dumps([{"id": self.item.id + 999, "qty": 1}])},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_cart_is_rejected(self):
        for payload in ["not-json", "{}", '[{"id": 1, "qty": 0}]', '[{"id": 1, "qty": 21}]']:
            response = self.client.post("/r/cafe-a/table/1/", {
                "name": "Test", "phone": "01700000000", "items": payload,
            })
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_order_total_is_calculated_server_side(self):
        response = self.client.post("/r/cafe-a/table/1/", {
            "name": "Test", "phone": "01700000000",
            "items": json.dumps([{"id": self.item.id, "qty": 2}]),
        })
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(str(order.total), "200.00")

    def test_waiter_cannot_access_dashboard_or_kot(self):
        RestaurantMembership.objects.create(restaurant=self.a, user=self.user, role="waiter")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/dashboard/cafe-a/").status_code, 404)
        self.assertEqual(self.client.get("/dashboard/cafe-a/kot/").status_code, 404)

    def test_kitchen_role_can_access_kot_but_not_dashboard(self):
        RestaurantMembership.objects.create(restaurant=self.a, user=self.user, role="kitchen")
        self.client.force_login(self.user)
        self.assertEqual(self.client.get("/dashboard/cafe-a/kot/").status_code, 200)
        self.assertEqual(self.client.get("/dashboard/cafe-a/").status_code, 404)

    def test_order_status_is_tenant_scoped(self):
        order = Order.objects.create(restaurant=self.a, table=self.table, customer_name="A", customer_phone="01700000000")
        RestaurantMembership.objects.create(restaurant=self.b, user=self.user, role="owner")
        self.client.force_login(self.user)
        response = self.client.post(f"/dashboard/cafe-b/status/{order.id}/", {"status": "paid"})
        self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, "pending")

    def test_subscription_grace_period(self):
        plan = Plan.objects.create(name="Starter", monthly_price="0.00")
        from django.utils import timezone
        from datetime import timedelta
        subscription = Subscription.objects.create(
            restaurant=self.a, plan=plan, ends_at=timezone.now() - timedelta(days=1), grace_days=3,
        )
        self.assertTrue(subscription.in_grace)
        subscription.grace_days = 0
        subscription.save()
        self.assertFalse(subscription.in_grace)

    def test_customer_demo_is_available_without_a_restaurant_account(self):
        response = self.client.get("/demo/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The Demo Kitchen")
        self.assertContains(response, "Classic Beef Burger")
        self.assertEqual(Order.objects.count(), 0)

    def test_home_page_links_directly_to_customer_demo(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "/demo/")
        self.assertContains(response, "Try Customer Demo")


# ---------------------------------------------------------------------------
# v2: secure table URLs, cooking notes, live feed, subscriptions, payments
# ---------------------------------------------------------------------------
from datetime import timedelta
from io import StringIO

from django.core import mail
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from .models import PaymentTransaction, ServiceRequest


class BaseCase(TestCase):
    def setUp(self):
        self.a = Restaurant.objects.create(name="Cafe A", slug="cafe-a")
        self.b = Restaurant.objects.create(name="Cafe B", slug="cafe-b")
        self.table = DiningTable.objects.create(restaurant=self.a, number=1)
        self.table_b = DiningTable.objects.create(restaurant=self.b, number=1)
        self.category = Category.objects.create(restaurant=self.a, name="Food")
        self.item = MenuItem.objects.create(restaurant=self.a, category=self.category, name="Rice", price="100.00")
        self.owner = get_user_model().objects.create_user(username="owner", password="test-pass-123", email="o@example.com")
        RestaurantMembership.objects.create(restaurant=self.a, user=self.owner, role="owner")
        self.admin = get_user_model().objects.create_user(username="root", password="test-pass-123", is_staff=True)

    def order(self, **extra):
        data = {"name": "Test", "phone": "01700000000",
                "items": json.dumps([{"id": self.item.id, "qty": 2, "note": "Less spicy"}])}
        data.update(extra)
        return self.client.post(self.table_url(), data)

    def table_url(self):
        return f"/r/cafe-a/t/{self.table.token}/"


class SecureTableUrlTests(BaseCase):
    def test_token_url_loads_and_embeds_table_number(self):
        response = self.client.get(self.table_url())
        self.assertContains(response, "Table 1")

    def test_wrong_token_or_other_restaurant_is_404(self):
        self.assertEqual(self.client.get("/r/cafe-a/t/00000000-0000-4000-8000-000000000000/").status_code, 404)
        self.assertEqual(self.client.get(f"/r/cafe-a/t/{self.table_b.token}/").status_code, 404)

    def test_disabled_table_is_404(self):
        self.table.is_active = False
        self.table.save()
        self.assertEqual(self.client.get(self.table_url()).status_code, 404)

    def test_qr_pdf_uses_token_urls(self):
        self.assertIn(str(self.table.token), self.table.qr_url())
        self.client.force_login(self.owner)
        response = self.client.get("/dashboard/cafe-a/qr.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_table_tokens_are_unique(self):
        self.assertNotEqual(self.table.token, self.table_b.token)


class CookingNoteAndStockTests(BaseCase):
    def test_note_is_saved_and_total_is_server_side(self):
        self.assertEqual(self.order().status_code, 302)
        order = Order.objects.get()
        line = order.items.get()
        self.assertEqual(line.note, "Less spicy")
        self.assertEqual(str(order.total), "200.00")

    def test_note_is_truncated(self):
        self.order(items=json.dumps([{"id": self.item.id, "qty": 1, "note": "x" * 999}]))
        self.assertEqual(len(Order.objects.get().items.get().note), 250)

    def test_out_of_stock_item_cannot_be_ordered(self):
        self.item.is_available = False
        self.item.save()
        self.assertEqual(self.order().status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_sold_out_item_is_shown_as_out_of_stock(self):
        self.item.is_available = False
        self.item.save()
        self.assertContains(self.client.get(self.table_url()), "স্টক শেষ")

    def test_owner_can_toggle_stock_and_edit_price(self):
        self.client.force_login(self.owner)
        self.client.post("/dashboard/cafe-a/manage/", {"action": "toggle_item", "item_id": self.item.id})
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_available)
        self.client.post("/dashboard/cafe-a/manage/", {"action": "edit_item", "item_id": self.item.id, "name": "Rice Bowl", "price": "150"})
        self.item.refresh_from_db()
        self.assertEqual((self.item.name, str(self.item.price)), ("Rice Bowl", "150.00"))

    def test_owner_cannot_edit_other_restaurants_item(self):
        other = MenuItem.objects.create(restaurant=self.b, category=Category.objects.create(restaurant=self.b, name="X"), name="Tea", price="10")
        self.client.force_login(self.owner)
        response = self.client.post("/dashboard/cafe-a/manage/", {"action": "edit_item", "item_id": other.id, "name": "Hacked", "price": "1"})
        self.assertEqual(response.status_code, 404)
        other.refresh_from_db()
        self.assertEqual(other.name, "Tea")


class LiveAndTrackingTests(BaseCase):
    def test_live_feed_requires_login_and_role(self):
        self.assertEqual(self.client.get("/dashboard/cafe-a/live.json").status_code, 401)
        waiter = get_user_model().objects.create_user(username="w", password="test-pass-123")
        RestaurantMembership.objects.create(restaurant=self.a, user=waiter, role="waiter")
        self.client.force_login(waiter)
        self.assertEqual(self.client.get("/dashboard/cafe-a/live.json").status_code, 404)

    def test_live_feed_is_tenant_scoped(self):
        self.order()
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/dashboard/cafe-b/live.json").status_code, 404)
        data = self.client.get("/dashboard/cafe-a/live.json").json()
        self.assertEqual(data["pending_count"], 1)
        self.assertIn("Less spicy", data["html"])
        self.assertEqual(data["latest_order_id"], Order.objects.get().id)

    def test_status_flow_and_json_response(self):
        self.order()
        order = Order.objects.get()
        self.client.force_login(self.owner)
        response = self.client.post(f"/dashboard/cafe-a/status/{order.id}/", {"status": "accepted"}, headers={"x-requested-with": "fetch"})
        self.assertEqual(response.json()["status"], "accepted")
        self.client.post(f"/dashboard/cafe-a/status/{order.id}/", {"status": "paid"})  # illegal jump
        order.refresh_from_db()
        self.assertEqual(order.status, "accepted")

    def test_customer_tracking_status_json(self):
        self.order()
        order = Order.objects.get()
        url = f"/r/cafe-a/track/{order.public_token}/status.json"
        self.assertEqual(self.client.get(url).json()["step"], 0)
        order.status = "preparing"
        order.save()
        data = self.client.get(url).json()
        self.assertEqual((data["step"], data["label"]), (2, "Cooking"))
        self.assertEqual(self.client.get(f"/r/cafe-b/track/{order.public_token}/status.json").status_code, 404)

    def test_service_request_via_token_and_dedupe(self):
        url = f"{self.table_url()}service/bill/"
        self.assertEqual(self.client.post(url, headers={"x-requested-with": "fetch"}).json()["created"], True)
        self.assertEqual(self.client.post(url, headers={"x-requested-with": "fetch"}).json()["created"], False)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(self.client.post(f"{self.table_url()}service/pizza/").status_code, 404)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_staff_can_resolve_service_request(self):
        request = ServiceRequest.objects.create(restaurant=self.a, table=self.table, kind="waiter")
        self.client.force_login(self.owner)
        self.client.post(f"/dashboard/cafe-a/service/{request.id}/resolve/")
        request.refresh_from_db()
        self.assertTrue(request.resolved)
        self.assertIsNotNone(request.resolved_at)

    def test_kot_page_renders_with_services(self):
        self.order()
        ServiceRequest.objects.create(restaurant=self.a, table=self.table, kind="bill")
        self.client.force_login(self.owner)
        response = self.client.get("/dashboard/cafe-a/kot/")
        self.assertContains(response, "বিল চান")
        self.assertContains(response, "Less spicy")


class SubscriptionTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(name="Pro", monthly_price="500.00", duration_days=30)

    def test_subscription_status_and_days_left(self):
        sub = Subscription.objects.create(restaurant=self.a, plan=self.plan, ends_at=timezone.now() + timedelta(days=5, hours=1))
        self.assertEqual((sub.status, sub.days_left), ("active", 6))
        self.assertTrue(sub.expires_within(7))
        sub.ends_at = timezone.now() - timedelta(days=1)
        self.assertEqual(sub.status, "grace")
        sub.ends_at = timezone.now() - timedelta(days=10)
        self.assertEqual(sub.status, "expired")

    @override_settings(ENFORCE_SUBSCRIPTIONS=True)
    def test_orders_blocked_without_valid_subscription_when_enforced(self):
        self.assertEqual(self.order().status_code, 403)
        Subscription.objects.create(restaurant=self.a, plan=self.plan, ends_at=timezone.now() + timedelta(days=3))
        self.assertEqual(self.order().status_code, 302)

    def test_orders_allowed_without_subscription_by_default(self):
        self.assertEqual(self.order().status_code, 302)

    def test_plan_limits_menu_items(self):
        self.plan.max_menu_items = 1
        self.plan.save()
        Subscription.objects.create(restaurant=self.a, plan=self.plan, ends_at=timezone.now() + timedelta(days=3))
        self.client.force_login(self.owner)
        self.client.post("/dashboard/cafe-a/manage/", {"action": "menu", "name": "Dal", "price": "50", "category": self.category.id})
        self.assertEqual(self.a.menu_items.count(), 1)

    def test_expiry_alert_command_sends_once_and_skips_renewed(self):
        Subscription.objects.create(restaurant=self.a, plan=self.plan, ends_at=timezone.now() + timedelta(days=2))
        call_command("check_subscriptions", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Cafe A", mail.outbox[0].subject)
        call_command("check_subscriptions", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)


class PaymentTests(BaseCase):
    def setUp(self):
        super().setUp()
        self.plan = Plan.objects.create(name="Pro", monthly_price="500.00", duration_days=30)

    def submit(self, **extra):
        data = {"plan": self.plan.id, "method": "bkash", "sender_number": "01711111111", "trx_id": "8n7a6d5e4f"}
        data.update(extra)
        return self.client.post("/dashboard/cafe-a/billing/", data)

    def test_owner_submits_payment_and_trx_is_normalised(self):
        self.client.force_login(self.owner)
        self.submit()
        payment = PaymentTransaction.objects.get()
        self.assertEqual((payment.trx_id, str(payment.amount), payment.status), ("8N7A6D5E4F", "500.00", "pending"))

    def test_duplicate_trx_and_bad_input_rejected(self):
        self.client.force_login(self.owner)
        self.submit()
        self.submit()
        self.submit(trx_id="x", sender_number="abc")
        self.submit(method="cash")
        self.assertEqual(PaymentTransaction.objects.count(), 1)

    def test_only_owner_sees_billing(self):
        cashier = get_user_model().objects.create_user(username="c", password="test-pass-123")
        RestaurantMembership.objects.create(restaurant=self.a, user=cashier, role="cashier")
        self.client.force_login(cashier)
        self.assertEqual(self.client.get("/dashboard/cafe-a/billing/").status_code, 404)

    def test_admin_verifies_payment_and_subscription_starts(self):
        self.client.force_login(self.owner)
        self.submit()
        self.client.force_login(self.admin)
        payment = PaymentTransaction.objects.get()
        self.client.post(f"/control/payments/{payment.id}/verify/")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "verified")
        self.assertEqual(payment.reviewed_by, self.admin)
        subscription = self.a.current_subscription
        self.assertEqual(subscription.days_left, 30)
        # Verifying twice must not extend twice.
        self.client.post(f"/control/payments/{payment.id}/verify/")
        self.assertEqual(self.a.subscriptions.count(), 1)

    def test_renewal_extends_from_current_end_date(self):
        first = Subscription.start(self.a, self.plan)
        second = Subscription.start(self.a, self.plan)
        self.assertEqual(second.starts_at, first.ends_at)
        self.assertEqual(second.days_left, 60)

    def test_rejected_trx_can_be_resubmitted(self):
        self.client.force_login(self.owner)
        self.submit()
        PaymentTransaction.objects.get().reject(self.admin, "wrong amount")
        self.submit()
        self.assertEqual(PaymentTransaction.objects.count(), 2)

    def test_non_admin_cannot_verify(self):
        self.client.force_login(self.owner)
        self.submit()
        payment = PaymentTransaction.objects.get()
        self.client.post(f"/control/payments/{payment.id}/verify/")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "pending")

    def test_control_page_lists_pending_payment(self):
        self.client.force_login(self.owner)
        self.submit()
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/control/"), "8N7A6D5E4F")


class DatabaseSettingsTests(TestCase):
    """The DATABASE_URL switch must work without touching application code."""

    def test_database_url_selects_engine(self):
        import dj_database_url
        pg = dj_database_url.parse("postgresql://u:p@db.example.com:5432/om")
        self.assertIn("postgresql", pg["ENGINE"])
        self.assertEqual(pg["NAME"], "om")
        lite = dj_database_url.parse("sqlite:///x.sqlite3")
        self.assertIn("sqlite3", lite["ENGINE"])

    def test_settings_fall_back_to_sqlite_without_database_url(self):
        import importlib, os
        from unittest import mock
        import config.settings as cfg
        with mock.patch.dict(os.environ, {"DATABASE_URL": ""}):
            reloaded = importlib.reload(cfg)
            self.assertIn("sqlite3", reloaded.DATABASES["default"]["ENGINE"])
        with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://u:p@h:5432/n"}):
            reloaded = importlib.reload(cfg)
            self.assertIn("postgresql", reloaded.DATABASES["default"]["ENGINE"])
        importlib.reload(cfg)
