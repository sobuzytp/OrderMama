from django.urls import re_path
from .consumers import RestaurantConsumer
websocket_urlpatterns=[re_path(r"ws/orders/(?P<slug>[-\w]+)/$",RestaurantConsumer.as_asgi())]
