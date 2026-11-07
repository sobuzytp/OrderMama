from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
@receiver(post_save,sender=Order)
def notify(sender,instance,**kwargs):
 layer=get_channel_layer()
 if layer: async_to_sync(layer.group_send)("restaurant_"+instance.restaurant.slug,{"type":"order.update","data":{"id":instance.pk,"status":instance.status}})
