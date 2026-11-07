from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.menu.models import MenuItem

from .models import Order, ServiceRequest


@receiver(post_save, sender=Order)
def order_saved(sender, instance, created, **kwargs):
    if created:
        return  # নতুন অর্ডার place_order() থেকে ব্রডকাস্ট হয় (আইটেম তৈরির পরে)
    fields = kwargs.get("update_fields")
    if fields and set(fields) <= {"subtotal", "updated_at"}:
        return  # শুধু মোট হিসাব হালনাগাদ — স্ট্যাটাস বদল নয়
    from apps.realtime.broadcast import broadcast_order_update

    transaction.on_commit(lambda: broadcast_order_update(instance))


@receiver(post_save, sender=ServiceRequest)
def service_request_saved(sender, instance, created, **kwargs):
    from apps.realtime.broadcast import broadcast_service_request

    transaction.on_commit(lambda: broadcast_service_request(instance, created))


@receiver(post_save, sender=MenuItem)
def menu_item_saved(sender, instance, **kwargs):
    from apps.realtime.broadcast import broadcast_menu_change

    transaction.on_commit(lambda: broadcast_menu_change(instance))
