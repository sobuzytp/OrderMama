from django.urls import path

from . import portal_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("demo/", views.demo_menu, name="demo_menu"),

    # Platform (Super Admin)
    path("control/", portal_views.control, name="control"),
    path("control/restaurants/create/", portal_views.create_restaurant, name="create_restaurant"),
    path("control/payments/<int:pk>/<str:action>/", portal_views.review_payment, name="review_payment"),

    # Customer: secure QR link (table token) and the older table-number link.
    path("r/<slug:slug>/t/<uuid:token>/", views.menu_by_token, name="menu_by_token"),
    path("r/<slug:slug>/t/<uuid:token>/service/<str:kind>/", views.service_by_token, name="service_by_token"),
    path("r/<slug:slug>/table/<int:number>/", views.menu, name="menu"),
    path("r/<slug:slug>/service/<int:number>/<str:kind>/", views.service, name="service"),
    path("r/<slug:slug>/track/<uuid:token>/", views.track, name="track"),
    path("r/<slug:slug>/track/<uuid:token>/status.json", views.track_status, name="track_status"),

    # Restaurant staff
    path("dashboard/<slug:slug>/", views.dashboard, name="dashboard"),
    path("dashboard/<slug:slug>/manage/", portal_views.manage_restaurant, name="manage_restaurant"),
    path("dashboard/<slug:slug>/billing/", portal_views.billing, name="billing"),
    path("dashboard/<slug:slug>/kot/", views.kot, name="kot"),
    path("dashboard/<slug:slug>/live.json", views.live_feed, name="live_feed"),
    path("dashboard/<slug:slug>/status/<int:pk>/", views.status, name="status"),
    path("dashboard/<slug:slug>/service/<int:pk>/resolve/", views.resolve_service, name="resolve_service"),
    path("dashboard/<slug:slug>/qr.pdf", views.qr_pdf, name="qr_pdf"),
]
