from django.contrib.auth.views import LogoutView
from django.urls import include, path

from . import sa_views, views

dashboard_patterns = ([
    path("", views.dashboard_home, name="home"),
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
    path("register/", views.register_page, name="register"),
    path("dashboard/", include(dashboard_patterns)),
    path("superadmin/", include(superadmin_patterns)),
    # কাস্টমার: ধরন /restaurant-slug/table-5/ (সবার শেষে, যাতে অন্য পাথের সাথে না মেশে)
    path("<slug:slug>/table-<int:number>/", views.customer_menu, name="customer_table"),
    path("<slug:slug>/", views.customer_menu, name="customer_menu"),
]
