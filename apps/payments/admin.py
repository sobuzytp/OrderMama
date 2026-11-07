from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("tran_id", "restaurant", "plan", "amount", "gateway", "status", "created_at")
    list_filter = ("status", "gateway")
    readonly_fields = ("tran_id",)
