from django.db import IntegrityError, transaction

from apps.menu.models import MenuItem

from .models import Bill, Order, OrderItem, ServiceRequest

MAX_QTY = 50
MAX_LINES = 40


class OrderError(Exception):
    pass


def order_payload(order):
    """WebSocket ও API-তে ব্যবহারের জন্য অর্ডারের ডিকশনারি।"""
    return {
        "id": order.pk,
        "table": order.table.number,
        "table_name": order.table.display_name,
        "bill_id": order.bill_id,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "note": order.note,
        "status": order.status,
        "status_label": order.get_status_display(),
        "reject_reason": order.reject_reason,
        "subtotal": str(order.subtotal),
        "created_at": order.created_at.isoformat(),
        "items": [
            {
                "id": i.pk,
                "menu_item": i.menu_item_id,
                "name": i.name,
                "quantity": i.quantity,
                "unit_price": str(i.unit_price),
                "note": i.note,
            }
            for i in order.items.all()
        ],
    }


def _open_bill(table):
    try:
        with transaction.atomic():
            return Bill.open_for_table(table)
    except IntegrityError:
        return Bill.objects.filter(table=table).exclude(status=Bill.Status.PAID).get()


@transaction.atomic
def place_order(*, restaurant, table, customer_name, customer_phone, items, note=""):
    """items: [{"id": int, "qty": int, "note": str}]. দাম সবসময় ডেটাবেজ থেকে নেওয়া হয়।"""
    if table.restaurant_id != restaurant.pk or not table.is_active:
        raise OrderError("টেবিলটি পাওয়া যায়নি।")
    if not items:
        raise OrderError("কার্ট খালি।")
    if len(items) > MAX_LINES:
        raise OrderError("একসাথে অনেক বেশি আইটেম।")

    ids = [int(i["id"]) for i in items]
    menu = {
        m.pk: m
        for m in MenuItem.objects.filter(restaurant=restaurant, pk__in=ids, is_active=True)
    }

    lines = []
    for raw in items:
        item = menu.get(int(raw["id"]))
        if item is None:
            raise OrderError("একটি আইটেম মেনুতে নেই।")
        if item.is_stock_out:
            raise OrderError(f"“{item.name}” এখন স্টকে নেই।")
        qty = int(raw.get("qty", 1))
        if qty < 1 or qty > MAX_QTY:
            raise OrderError("পরিমাণ ১ থেকে ৫০ এর মধ্যে হতে হবে।")
        lines.append((item, qty, (raw.get("note") or "")[:200]))

    bill = _open_bill(table)
    if bill.status == Bill.Status.REQUESTED:
        # নতুন অর্ডার এলে বিল আবার খোলা অবস্থায় ফেরে
        bill.status = Bill.Status.OPEN
        bill.save(update_fields=["status"])

    order = Order.objects.create(
        restaurant=restaurant,
        table=table,
        bill=bill,
        customer_name=customer_name.strip()[:80],
        customer_phone=customer_phone.strip()[:20],
        note=(note or "")[:300],
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(order=order, menu_item=m, name=m.name, unit_price=m.price, quantity=q, note=n)
            for m, q, n in lines
        ]
    )
    order.recalc()

    from apps.realtime.broadcast import broadcast_new_order

    transaction.on_commit(lambda: broadcast_new_order(order))
    return order


@transaction.atomic
def change_status(order, new_status, *, reason=""):
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.can_move_to(new_status):
        raise OrderError(f"“{order.get_status_display()}” থেকে এই ধাপে যাওয়া যাবে না।")
    order.status = new_status
    if new_status == Order.Status.REJECTED:
        order.reject_reason = reason[:200]
    order.save()
    return order


@transaction.atomic
def request_bill(table):
    bill = _open_bill(table)
    if not bill.orders.exclude(status=Order.Status.REJECTED).exists():
        raise OrderError("এখনো কোনো অর্ডার নেই।")
    bill.status = Bill.Status.REQUESTED
    bill.save(update_fields=["status"])
    req = ServiceRequest.objects.create(
        restaurant=table.restaurant, table=table, kind=ServiceRequest.Kind.BILL
    )
    return req


def call_waiter(table):
    return ServiceRequest.objects.create(
        restaurant=table.restaurant, table=table, kind=ServiceRequest.Kind.WAITER
    )
