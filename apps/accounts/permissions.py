"""রোল-ভিত্তিক পারমিশন। কিচেন স্টাফ শুধু অর্ডার দেখবে, অ্যানালিটিক্স নয়।"""
from rest_framework.permissions import BasePermission

from .models import User

R = User.Role


class IsStaffOfRestaurant(BasePermission):
    """লগইন করা, সক্রিয়, রেস্টুরেন্টে যুক্ত স্টাফ।"""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.restaurant_id)


def roles_permission(*roles):
    class _P(IsStaffOfRestaurant):
        def has_permission(self, request, view):
            return super().has_permission(request, view) and request.user.role in roles

    _P.__name__ = "Roles_" + "_".join(roles)
    return _P


ManagerPermission = roles_permission(R.OWNER, R.MANAGER)
OrderStaffPermission = roles_permission(R.OWNER, R.MANAGER, R.CASHIER, R.KITCHEN, R.WAITER)
ServiceStaffPermission = roles_permission(R.OWNER, R.MANAGER, R.CASHIER, R.WAITER)
BillingPermission = roles_permission(R.OWNER, R.MANAGER, R.CASHIER)


class IsPlatformAdmin(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_active and u.is_superuser)


# কোন রোল কোন স্ট্যাটাসে অর্ডার নিয়ে যেতে পারে
STATUS_ROLES = {
    "accepted": {R.OWNER, R.MANAGER, R.CASHIER, R.WAITER},
    "rejected": {R.OWNER, R.MANAGER, R.CASHIER, R.WAITER, R.KITCHEN},
    "preparing": {R.OWNER, R.MANAGER, R.KITCHEN},
    "ready": {R.OWNER, R.MANAGER, R.KITCHEN},
    "served": {R.OWNER, R.MANAGER, R.WAITER, R.CASHIER},
    "paid": {R.OWNER, R.MANAGER, R.CASHIER},
}
