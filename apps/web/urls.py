from django.contrib.auth.views import LogoutView
from django.urls import include, path

from . import sa_views, views

dashboard_patterns = ([
    path("", views.merchant_root),
    path("dashboard/", views.dashboard_home, name="home"),
    path("login/", views.StaffLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("live/", views.live, name="live"),
    path("bills/", views.bills, name="bills"),
    path("menu/", views.menu_manage, name="menu"),
    path("tables/", views.tables, name="tables"),
    path("analytics/", views.analytics, name="analytics"),
    path("branding/", views.branding, name="branding"),
    path("staff/", views.staff, name="staff"),
    path("billing/", views.billing, name="billing"),
], "dashboard")

superadmin_patterns = ([
    path("", sa_views.home, name="home"),
    path("restaurants/", sa_views.restaurants, name="restaurants"),
    path("plans/", sa_views.plans, name="plans"),
    path("payments/", sa_views.payments, name="payments"),
], "superadmin")

urlpatterns = [
    path("", views.landing, name="landing"),
    path("healthz/", views.healthz),
    path("pwa-icon-<int:size>.png", views.pwa_icon, name="pwa_icon"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("register/", views.register_page, name="register"),
    path("merchant/", include(dashboard_patterns)),
    path("super-admin/", include(superadmin_patterns)),
    # কাস্টমার (লগইন ছাড়া): /restaurant-slug/ এবং /restaurant-slug/<table-uuid>/ — সবার শেষে
    path("<slug:slug>/<uuid:token>/", views.customer_menu, name="customer_table"),
    path("<slug:slug>/", views.customer_menu, name="customer_menu"),
]
