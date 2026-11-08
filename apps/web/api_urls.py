from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api_customer as c
from . import api_dashboard as d
from . import api_superadmin as sa

router = DefaultRouter()
router.register("categories", d.CategoryViewSet, basename="category")
router.register("menu-items", d.MenuItemViewSet, basename="menuitem")
router.register("tables", d.TableViewSet, basename="table")
router.register("staff", d.StaffViewSet, basename="staff")

urlpatterns = [
    # কাস্টমার
    path("c/<slug:slug>/menu/", c.MenuView.as_view()),
    path("c/<slug:slug>/t/<uuid:token>/session/", c.SessionView.as_view()),
    path("c/<slug:slug>/t/<uuid:token>/orders/", c.OrdersView.as_view()),
    path("c/<slug:slug>/t/<uuid:token>/call-waiter/", c.CallWaiterView.as_view()),
    path("c/<slug:slug>/t/<uuid:token>/request-bill/", c.RequestBillView.as_view()),
    path("register/", sa.RegisterView.as_view()),
    # স্টাফ
    path("d/orders/", d.OrderListView.as_view()),
    path("d/pulse/", d.PulseView.as_view()),
    path("d/orders/<int:pk>/status/", d.OrderStatusView.as_view()),
    path("d/service-requests/", d.ServiceRequestListView.as_view()),
    path("d/service-requests/<int:pk>/resolve/", d.ServiceRequestResolveView.as_view()),
    path("d/bills/", d.BillListView.as_view()),
    path("d/bills/<int:pk>/pay/", d.BillPayView.as_view()),
    path("d/qr/", d.QRPdfView.as_view()),
    path("d/branding/", d.BrandingView.as_view()),
    path("d/analytics/", d.AnalyticsView.as_view()),
    path("d/", include(router.urls)),
    # সুপার অ্যাডমিন
    path("sa/stats/", sa.StatsView.as_view()),
    path("sa/restaurants/", sa.RestaurantListView.as_view()),
    path("sa/restaurants/<int:pk>/approve/", sa.ApproveView.as_view()),
    path("sa/restaurants/<int:pk>/extend/", sa.ExtendView.as_view()),
    path("sa/restaurants/<int:pk>/block/", sa.BlockView.as_view()),
    path("sa/restaurants/<int:pk>/unblock/", sa.UnblockView.as_view()),
    path("sa/plans/", sa.PlanListView.as_view()),
    path("sa/plans/<int:pk>/", sa.PlanDetailView.as_view()),
    path("sa/payments/", sa.PaymentListView.as_view()),
]
