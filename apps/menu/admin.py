from django.contrib import admin

from .models import Category, MenuItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "position", "is_active")
    list_filter = ("restaurant",)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "category", "price", "is_veg", "is_stock_out")
    list_filter = ("restaurant", "is_veg", "is_stock_out")
    search_fields = ("name",)
