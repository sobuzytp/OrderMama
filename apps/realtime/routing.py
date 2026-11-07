from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/c/", consumers.CustomerConsumer.as_asgi()),
    path("ws/dashboard/", consumers.StaffConsumer.as_asgi()),
]
