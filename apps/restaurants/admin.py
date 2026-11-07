from django.contrib import admin

from .models import Restaurant, Table


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_approved", "is_blocked", "created_at")
    list_filter = ("is_approved", "is_blocked")
    search_fields = ("name", "slug", "phone")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "number", "label", "is_active")
    list_filter = ("restaurant", "is_active")
