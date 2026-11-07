# Generated as the initial schema for OrderMama.
import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Plan", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=80)),
            ("monthly_price", models.DecimalField(decimal_places=2, max_digits=10)),
            ("live_orders", models.BooleanField(default=False)),
            ("branding", models.BooleanField(default=False)),
            ("active", models.BooleanField(default=True)),
        ]),
        migrations.CreateModel(name="Restaurant", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=160)),
            ("slug", models.SlugField(unique=True)),
            ("logo", models.ImageField(blank=True, null=True, upload_to="logos/")),
            ("cover_image", models.ImageField(blank=True, null=True, upload_to="covers/")),
            ("primary_color", models.CharField(default="#E85D04", max_length=7)),
            ("secondary_color", models.CharField(default="#292522", max_length=7)),
            ("theme", models.CharField(choices=[("light", "Light"), ("dark", "Dark")], default="light", max_length=8)),
            ("welcome_message", models.CharField(default="স্বাগতম!", max_length=200)),
            ("is_active", models.BooleanField(default=True)),
        ]),
        migrations.CreateModel(name="Category", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=100)),
            ("sort_order", models.PositiveIntegerField(default=0)),
            ("is_active", models.BooleanField(default=True)),
            ("restaurant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="categories", to="core.restaurant")),
        ], options={"ordering": ["sort_order", "name"]}),
        migrations.CreateModel(name="DiningTable", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("number", models.PositiveIntegerField()),
            ("token", models.UUIDField(default=uuid.uuid4, editable=False)),
            ("is_active", models.BooleanField(default=True)),
            ("restaurant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tables", to="core.restaurant")),
        ]),
        migrations.CreateModel(name="MenuItem", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=140)),
            ("description", models.TextField(blank=True)),
            ("image", models.ImageField(blank=True, null=True, upload_to="menu/")),
            ("price", models.DecimalField(decimal_places=2, max_digits=10)),
            ("is_vegetarian", models.BooleanField(default=True)),
            ("is_available", models.BooleanField(default=True)),
            ("category", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="items", to="core.category")),
            ("restaurant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menu_items", to="core.restaurant")),
        ]),
        migrations.CreateModel(name="RestaurantMembership", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("role", models.CharField(choices=[("owner", "Owner"), ("manager", "Manager"), ("cashier", "Cashier"), ("kitchen", "Kitchen"), ("waiter", "Waiter")], max_length=12)),
            ("restaurant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="core.restaurant")),
            ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ]),
        migrations.CreateModel(name="Subscription", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("starts_at", models.DateTimeField(default=django.utils.timezone.now)),
            ("ends_at", models.DateTimeField()),
            ("grace_days", models.PositiveSmallIntegerField(default=3)),
            ("active", models.BooleanField(default=True)),
            ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.plan")),
            ("restaurant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="subscriptions", to="core.restaurant")),
        ]),
        migrations.CreateModel(name="Order", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("customer_name", models.CharField(max_length=100)),
            ("customer_phone", models.CharField(max_length=20)),
            ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("preparing", "Preparing"), ("ready", "Ready"), ("served", "Served"), ("paid", "Paid"), ("rejected", "Rejected")], default="pending", max_length=12)),
            ("total", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
            ("public_token", models.UUIDField(default=uuid.uuid4, unique=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("restaurant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="orders", to="core.restaurant")),
            ("table", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.diningtable")),
        ], options={"ordering": ["-created_at"]}),
        migrations.CreateModel(name="OrderItem", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("item_name", models.CharField(max_length=140)),
            ("unit_price", models.DecimalField(decimal_places=2, max_digits=10)),
            ("quantity", models.PositiveIntegerField()),
            ("note", models.CharField(blank=True, max_length=250)),
            ("menu_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="core.menuitem")),
            ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="core.order")),
        ]),
        migrations.CreateModel(name="ServiceRequest", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("kind", models.CharField(choices=[("waiter", "Waiter"), ("bill", "Bill")], max_length=10)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("resolved", models.BooleanField(default=False)),
            ("restaurant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.restaurant")),
            ("table", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="core.diningtable")),
        ]),
        migrations.AddConstraint(model_name="restaurantmembership", constraint=models.UniqueConstraint(fields=("restaurant", "user"), name="unique_restaurant_user")),
        migrations.AddConstraint(model_name="diningtable", constraint=models.UniqueConstraint(fields=("restaurant", "number"), name="unique_restaurant_table")),
    ]
