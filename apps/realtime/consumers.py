from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.accounts.models import User
from apps.restaurants.models import Table

from .groups import menu_group, service_group, staff_group, table_group
from .tokens import read_table_token


class CustomerConsumer(AsyncJsonWebsocketConsumer):
    """কাস্টমার: মেনু-পরিবর্তন (স্টক আউট) + নিজের টেবিলের অর্ডার স্ট্যাটাস।"""

    async def connect(self):
        qs = self.scope["query_string"].decode()
        token = (parse_qs(qs).get("token") or [""])[0]  # URL-ডিকোড করা (: হয়ে আসে %3A)
        data = read_table_token(token)
        if not data or not await self._valid(data):
            await self.close(code=4403)
            return
        self.groups_joined = [menu_group(data["r"]), table_group(data["t"])]
        for g in self.groups_joined:
            await self.channel_layer.group_add(g, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def _valid(self, data):
        return Table.objects.filter(
            pk=data["t"], restaurant_id=data["r"], is_active=True
        ).exists()

    async def disconnect(self, code):
        for g in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(g, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def order_update(self, event):
        await self.send_json({"type": "order.update", "order": event["order"]})

    async def menu_change(self, event):
        await self.send_json({"type": "menu.change", "item_id": event["item_id"]})


class StaffConsumer(AsyncJsonWebsocketConsumer):
    """রেস্টুরেন্ট স্টাফ: লাইভ অর্ডার (KOT) ও সার্ভিস রিকোয়েস্ট।"""

    async def connect(self):
        user = self.scope.get("user")
        info = await self._info(user)
        if not info:
            await self.close(code=4403)
            return
        rid, role = info
        self.groups_joined = [staff_group(rid)]
        if role != User.Role.KITCHEN:
            self.groups_joined.append(service_group(rid))
        for g in self.groups_joined:
            await self.channel_layer.group_add(g, self.channel_name)
        await self.accept()

    @database_sync_to_async
    def _info(self, user):
        if not (user and user.is_authenticated and user.is_active and user.restaurant_id):
            return None
        if not user.restaurant.has_feature("live_orders"):
            return None
        return user.restaurant_id, user.role

    async def disconnect(self, code):
        for g in getattr(self, "groups_joined", []):
            await self.channel_layer.group_discard(g, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("type") == "ping":
            await self.send_json({"type": "pong"})

    async def order_new(self, event):
        await self.send_json({"type": "order.new", "order": event["order"]})

    async def order_update(self, event):
        await self.send_json({"type": "order.update", "order": event["order"]})

    async def service_new(self, event):
        await self.send_json({"type": "service.new", "request": event["request"]})
