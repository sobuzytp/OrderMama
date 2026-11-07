"""সিঙ্ক কোড (ভিউ/সিগন্যাল) থেকে WebSocket গ্রুপে ইভেন্ট পাঠানো। ব্রডকাস্ট ব্যর্থ হলে অর্ডার আটকাবে না।"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .groups import menu_group, service_group, staff_group, table_group

log = logging.getLogger(__name__)


def _send(group, message):
    try:
        layer = get_channel_layer()
        if layer is not None:
            async_to_sync(layer.group_send)(group, message)
    except Exception:  # Redis বন্ধ থাকলেও মূল কাজ চলবে
        log.exception("WebSocket ব্রডকাস্ট ব্যর্থ: %s", group)


def _payload(order):
    from apps.orders.models import Order
    from apps.orders.services import order_payload

    order = Order.objects.select_related("table").prefetch_related("items").get(pk=order.pk)
    return order_payload(order)


def broadcast_new_order(order):
    data = _payload(order)
    _send(staff_group(order.restaurant_id), {"type": "order.new", "order": data})
    _send(table_group(order.table_id), {"type": "order.update", "order": _customer_view(data)})


def broadcast_order_update(order):
    data = _payload(order)
    _send(staff_group(order.restaurant_id), {"type": "order.update", "order": data})
    _send(table_group(order.table_id), {"type": "order.update", "order": _customer_view(data)})


def _customer_view(data):
    """কাস্টমারকে অন্যের ফোন নম্বর দেখানো হয় না।"""
    d = dict(data)
    d.pop("customer_phone", None)
    return d


def broadcast_service_request(req, created):
    if not created:
        return
    _send(
        service_group(req.restaurant_id),
        {
            "type": "service.new",
            "request": {
                "id": req.pk,
                "kind": req.kind,
                "kind_label": req.get_kind_display(),
                "table": req.table.number,
                "table_name": req.table.display_name,
                "created_at": req.created_at.isoformat(),
            },
        },
    )


def broadcast_menu_change(item):
    _send(menu_group(item.restaurant_id), {"type": "menu.change", "item_id": item.pk})
