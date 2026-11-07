from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from .models import Category, DiningTable, MenuItem, Order, Restaurant, RestaurantMembership

User = get_user_model()

def platform_staff(user):
    return user.is_authenticated and user.is_staff

@user_passes_test(platform_staff, login_url="/accounts/login/")
def control(request):
    restaurants = Restaurant.objects.all().order_by("-id")
    return render(request, "control.html", {
        "restaurants": restaurants, "restaurant_count": restaurants.count(),
        "active_count": restaurants.filter(is_active=True).count(),
        "user_count": User.objects.count(), "order_count": Order.objects.count(),
    })

@user_passes_test(platform_staff, login_url="/accounts/login/")
def create_restaurant(request):
    if request.method != "POST":
        return redirect("control")
    name = request.POST.get("name", "").strip()
    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    email = request.POST.get("email", "").strip()
    try:
        count = int(request.POST.get("tables", "5"))
        if not name or not username or len(password) < 10 or count < 1 or count > 100:
            raise ValueError
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("control")
        from django.utils.text import slugify
        base = slugify(name) or "restaurant"
        slug, suffix = base, 2
        while Restaurant.objects.filter(slug=slug).exists():
            slug, suffix = f"{base}-{suffix}", suffix + 1
        with transaction.atomic():
            restaurant = Restaurant.objects.create(name=name, slug=slug)
            owner = User.objects.create_user(username=username, email=email, password=password)
            RestaurantMembership.objects.create(restaurant=restaurant, user=owner, role="owner")
            DiningTable.objects.bulk_create([DiningTable(restaurant=restaurant, number=n) for n in range(1, count + 1)])
        messages.success(request, f"Restaurant {name} created. Owner username: {username}")
    except (ValueError, TypeError):
        messages.error(request, "Check the form. Password must be at least 10 characters and table count 1–100.")
    return redirect("control")

@login_required
def manage_restaurant(request, slug):
    restaurant = get_object_or_404(Restaurant, slug=slug)
    membership = RestaurantMembership.objects.filter(user=request.user, restaurant=restaurant).first()
    if not request.user.is_staff and not (membership and membership.role in ["owner", "manager"]):
        from django.http import Http404
        raise Http404
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "category":
            name = request.POST.get("name", "").strip()
            if name:
                Category.objects.create(restaurant=restaurant, name=name)
                messages.success(request, "Category created.")
        elif action == "menu":
            try:
                price = Decimal(request.POST.get("price", "0"))
                category = get_object_or_404(Category, pk=request.POST.get("category"), restaurant=restaurant)
                name = request.POST.get("name", "").strip()
                if not name or price <= 0:
                    raise InvalidOperation
                MenuItem.objects.create(restaurant=restaurant, category=category, name=name,
                    description=request.POST.get("description", "").strip(), price=price)
                messages.success(request, "Menu item created.")
            except (InvalidOperation, TypeError, ValueError):
                messages.error(request, "Enter a valid menu item and price.")
        elif action == "table":
            try:
                number = int(request.POST.get("number", "0"))
                if number < 1:
                    raise ValueError
                DiningTable.objects.get_or_create(restaurant=restaurant, number=number)
                messages.success(request, "Table saved.")
            except (TypeError, ValueError):
                messages.error(request, "Enter a valid table number.")
        elif action == "toggle_item":
            item = get_object_or_404(MenuItem, pk=request.POST.get("item_id"), restaurant=restaurant)
            item.is_available = not item.is_available
            item.save(update_fields=["is_available"])
        elif action == "toggle_table":
            table = get_object_or_404(DiningTable, pk=request.POST.get("table_id"), restaurant=restaurant)
            table.is_active = not table.is_active
            table.save(update_fields=["is_active"])
        return redirect("manage_restaurant", slug=slug)
    return render(request, "manage.html", {"restaurant": restaurant,
        "categories": restaurant.categories.all(), "items": restaurant.menu_items.select_related("category").all(),
        "tables": restaurant.tables.all()})
