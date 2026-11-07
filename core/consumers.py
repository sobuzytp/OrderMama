from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from .models import RestaurantMembership

@database_sync_to_async
def can_view_orders(user, slug):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return RestaurantMembership.objects.filter(
        user=user, restaurant__slug=slug,
        role__in=["owner", "manager", "cashier", "kitchen"],
    ).exists()

class RestaurantConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        slug = self.scope["url_route"]["kwargs"]["slug"]
        if not await can_view_orders(self.scope.get("user"), slug):
            await self.close(code=4403)
            return
        self.group = "restaurant_" + slug
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def order_update(self, event):
        await self.send_json(event["data"])
