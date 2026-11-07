from django.contrib import admin, messages

from .models import (
    Category, DiningTable, MenuItem, Order, OrderItem, PaymentTransaction, Plan, Restaurant,
    RestaurantMembership, ServiceRequest, Subscription,
)


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(RestaurantMembership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "restaurant", "role")
    list_filter = ("role", "restaurant")


@admin.register(DiningTable)
class DiningTableAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "number", "is_active", "token")
    list_filter = ("restaurant", "is_active")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "sort_order", "is_active")
    list_filter = ("restaurant", "is_active")


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("name", "restaurant", "category", "price", "is_available")
    list_filter = ("restaurant", "is_available", "category")
    search_fields = ("name",)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "restaurant", "table", "customer_name", "status", "total", "created_at")
    list_filter = ("restaurant", "status")
    inlines = [OrderItemInline]


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "table", "kind", "resolved", "created_at")
    list_filter = ("restaurant", "kind", "resolved")


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "monthly_price", "duration_days", "max_tables", "max_menu_items", "active")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "plan", "starts_at", "ends_at", "active")
    list_filter = ("active", "plan")


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("restaurant", "method", "trx_id", "amount", "status", "submitted_at")
    list_filter = ("status", "method")
    search_fields = ("trx_id", "sender_number", "restaurant__name")
    actions = ["verify_selected", "reject_selected"]

    @admin.action(description="Verify selected payments (start/extend subscription)")
    def verify_selected(self, request, queryset):
        done = 0
        for payment in queryset.filter(status="pending"):
            payment.verify(request.user)
            done += 1
        self.message_user(request, f"{done} payment(s) verified.", messages.SUCCESS)

    @admin.action(description="Reject selected payments")
    def reject_selected(self, request, queryset):
        done = 0
        for payment in queryset.filter(status="pending"):
            payment.reject(request.user)
            done += 1
        self.message_user(request, f"{done} payment(s) rejected.", messages.SUCCESS)
