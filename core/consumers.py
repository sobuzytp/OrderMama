from channels.generic.websocket import AsyncJsonWebsocketConsumer
class RestaurantConsumer(AsyncJsonWebsocketConsumer):
 async def connect(self):
  self.group="restaurant_"+self.scope["url_route"]["kwargs"]["slug"]
  await self.channel_layer.group_add(self.group,self.channel_name); await self.accept()
 async def disconnect(self,code): await self.channel_layer.group_discard(self.group,self.channel_name)
 async def order_update(self,event): await self.send_json(event["data"])
