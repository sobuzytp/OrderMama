import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
from django.core.asgi import get_asgi_application
django=get_asgi_application()
from channels.routing import ProtocolTypeRouter,URLRouter
from channels.auth import AuthMiddlewareStack
from core.routing import websocket_urlpatterns
application=ProtocolTypeRouter({"http":django,"websocket":AuthMiddlewareStack(URLRouter(websocket_urlpatterns))})
