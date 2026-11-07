from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class OrderMamaUserAdmin(UserAdmin):
    list_display = ("username", "role", "restaurant", "is_active", "is_superuser")
    list_filter = ("role", "is_active", "restaurant")
    fieldsets = UserAdmin.fieldsets + (("OrderMama", {"fields": ("restaurant", "role", "phone")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("OrderMama", {"fields": ("restaurant", "role", "phone")}),
    )
