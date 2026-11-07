from django.apps import AppConfig


class OrdersConfig(AppConfig):
    name = "apps.orders"
    label = "orders"
    verbose_name = "অর্ডার"

    def ready(self):
        from . import signals  # noqa: F401
