"""Push order / service events to WebSocket clients (best effort).

Polling is the guaranteed delivery path (cPanel cannot serve WebSockets), so a
failure here must never break order creation.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Order, ServiceRequest

logger = logging.getLogger(__name__)


def _broadcast(slug, data):
    try:
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)("restaurant_" + slug, {"type": "order.update", "data": data})
    except Exception:  # noqa: BLE001 - channel layer problems must not block requests
        logger.warning("Could not broadcast live update for %s", slug, exc_info=True)


@receiver(post_save, sender=Order)
def notify_order(sender, instance, created, **kwargs):
    _broadcast(instance.restaurant.slug, {"kind": "order", "id": instance.pk, "status": instance.status, "new": created})


@receiver(post_save, sender=ServiceRequest)
def notify_service(sender, instance, created, **kwargs):
    _broadcast(instance.restaurant.slug, {"kind": "service", "id": instance.pk, "new": created})
