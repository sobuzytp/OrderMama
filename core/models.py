import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone
class Restaurant(models.Model):
 name=models.CharField(max_length=160); slug=models.SlugField(unique=True); logo=models.ImageField(upload_to="logos/",blank=True,null=True); cover_image=models.ImageField(upload_to="covers/",blank=True,null=True)
 primary_color=models.CharField(max_length=7,default="#E85D04"); secondary_color=models.CharField(max_length=7,default="#292522"); theme=models.CharField(max_length=8,choices=[("light","Light"),("dark","Dark")],default="light"); welcome_message=models.CharField(max_length=200,default="স্বাগতম!"); is_active=models.BooleanField(default=True)
 def __str__(self): return self.name
class RestaurantMembership(models.Model):
 ROLES=[(x,x.title()) for x in ["owner","manager","cashier","kitchen","waiter"]]
 restaurant=models.ForeignKey(Restaurant,on_delete=models.CASCADE,related_name="memberships"); user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.CASCADE); role=models.CharField(max_length=12,choices=ROLES)
 class Meta: constraints=[models.UniqueConstraint(fields=["restaurant","user"],name="unique_restaurant_user")]
class DiningTable(models.Model):
 restaurant=models.ForeignKey(Restaurant,on_delete=models.CASCADE,related_name="tables"); number=models.PositiveIntegerField(); token=models.UUIDField(default=uuid.uuid4,editable=False); is_active=models.BooleanField(default=True)
 class Meta: constraints=[models.UniqueConstraint(fields=["restaurant","number"],name="unique_restaurant_table")]
class Category(models.Model):
 restaurant=models.ForeignKey(Restaurant,on_delete=models.CASCADE,related_name="categories"); name=models.CharField(max_length=100); sort_order=models.PositiveIntegerField(default=0); is_active=models.BooleanField(default=True)
 class Meta: ordering=["sort_order","name"]
class MenuItem(models.Model):
 restaurant=models.ForeignKey(Restaurant,on_delete=models.CASCADE,related_name="menu_items"); category=models.ForeignKey(Category,on_delete=models.PROTECT,related_name="items"); name=models.CharField(max_length=140); description=models.TextField(blank=True); image=models.ImageField(upload_to="menu/",blank=True,null=True); price=models.DecimalField(max_digits=10,decimal_places=2); is_vegetarian=models.BooleanField(default=True); is_available=models.BooleanField(default=True)
class Order(models.Model):
 STATUSES=[(s,s.title()) for s in ["pending","accepted","preparing","ready","served","paid","rejected"]]
 restaurant=models.ForeignKey(Restaurant,on_delete=models.CASCADE,related_name="orders"); table=models.ForeignKey(DiningTable,on_delete=models.PROTECT); customer_name=models.CharField(max_length=100); customer_phone=models.CharField(max_length=20); status=models.CharField(max_length=12,choices=STATUSES,default="pending"); total=models.DecimalField(max_digits=12,decimal_places=2,default=0); public_token=models.UUIDField(default=uuid.uuid4,unique=True); created_at=models.DateTimeField(auto_now_add=True)
 class Meta: ordering=["-created_at"]
class OrderItem(models.Model):
 order=models.ForeignKey(Order,on_delete=models.CASCADE,related_name="items"); menu_item=models.ForeignKey(MenuItem,on_delete=models.PROTECT); item_name=models.CharField(max_length=140); unit_price=models.DecimalField(max_digits=10,decimal_places=2); quantity=models.PositiveIntegerField(); note=models.CharField(max_length=250,blank=True)
 @property
 def line_total(self): return self.unit_price*self.quantity
class ServiceRequest(models.Model):
 restaurant=models.ForeignKey(Restaurant,on_delete=models.CASCADE); table=models.ForeignKey(DiningTable,on_delete=models.CASCADE); kind=models.CharField(max_length=10,choices=[("waiter","Waiter"),("bill","Bill")]); created_at=models.DateTimeField(auto_now_add=True); resolved=models.BooleanField(default=False)
class Plan(models.Model):
 name=models.CharField(max_length=80); monthly_price=models.DecimalField(max_digits=10,decimal_places=2); live_orders=models.BooleanField(default=False); branding=models.BooleanField(default=False); active=models.BooleanField(default=True)
class Subscription(models.Model):
 restaurant=models.ForeignKey(Restaurant,on_delete=models.CASCADE,related_name="subscriptions"); plan=models.ForeignKey(Plan,on_delete=models.PROTECT); starts_at=models.DateTimeField(default=timezone.now); ends_at=models.DateTimeField(); grace_days=models.PositiveSmallIntegerField(default=3); active=models.BooleanField(default=True)
 @property
 def in_grace(self): return self.active and timezone.now()<=self.ends_at+timezone.timedelta(days=self.grace_days)
