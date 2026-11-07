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
