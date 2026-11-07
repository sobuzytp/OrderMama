from django.contrib import admin

from .models import Bill, Order, OrderItem, ServiceRequest


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant", "table", "customer_name", "status", "subtotal", "created_at")
    list_filter = ("restaurant", "status")
    inlines = [OrderItemInline]


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant", "table", "status", "opened_at", "paid_at")
    list_filter = ("restaurant", "status")


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "table", "kind", "is_resolved", "created_at")
    list_filter = ("restaurant", "kind", "is_resolved")
