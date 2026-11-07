from django.urls import path
from . import views, portal_views

urlpatterns = [
    path("", views.home, name="home"),
    path("control/", portal_views.control, name="control"),
    path("control/restaurants/create/", portal_views.create_restaurant, name="create_restaurant"),
    path("r/<slug:slug>/table/<int:number>/", views.menu, name="menu"),
    path("r/<slug:slug>/track/<uuid:token>/", views.track, name="track"),
    path("r/<slug:slug>/service/<int:number>/<str:kind>/", views.service, name="service"),
    path("dashboard/<slug:slug>/", views.dashboard, name="dashboard"),
    path("dashboard/<slug:slug>/manage/", portal_views.manage_restaurant, name="manage_restaurant"),
    path("dashboard/<slug:slug>/kot/", views.kot, name="kot"),
    path("dashboard/<slug:slug>/status/<int:pk>/", views.status, name="status"),
    path("dashboard/<slug:slug>/qr.pdf", views.qr_pdf, name="qr_pdf"),
]
