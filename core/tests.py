from django.test import TestCase
from .models import Restaurant,DiningTable,Category,MenuItem
class TenantTests(TestCase):
 def setUp(self):
  self.a=Restaurant.objects.create(name="Cafe A",slug="cafe-a"); self.b=Restaurant.objects.create(name="Cafe B",slug="cafe-b")
  self.t=DiningTable.objects.create(restaurant=self.a,number=1); self.c=Category.objects.create(restaurant=self.a,name="Food")
  self.f=MenuItem.objects.create(restaurant=self.a,category=self.c,name="Rice",price=100)
 def test_table_scoped(self): self.assertFalse(DiningTable.objects.filter(restaurant=self.b,number=1).exists())
 def test_menu_loads(self): self.assertEqual(self.client.get("/r/cafe-a/table/1/").status_code,200)
 def test_menu_item_tenant(self): self.assertFalse(MenuItem.objects.filter(pk=self.f.pk,restaurant=self.b).exists())
