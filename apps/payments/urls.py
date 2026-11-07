from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("start/", views.start_payment, name="start"),
    path("mock/<str:tran_id>/", views.mock_checkout, name="mock"),
    path("success/", views.success, name="success"),
    path("fail/", views.fail, name="fail"),
    path("cancel/", views.cancel, name="cancel"),
    path("ipn/", views.ipn, name="ipn"),
]
