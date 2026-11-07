from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie


def superadmin_page(template, title):
    def view(request):
        if not request.user.is_superuser:
            raise Http404
        return render(request, template, {"title": title, "sa_active": request.resolver_match.url_name})
    return login_required(login_url="/dashboard/login/")(ensure_csrf_cookie(view))


home = superadmin_page("superadmin/home.html", "ওভারভিউ")
restaurants = superadmin_page("superadmin/restaurants.html", "রেস্টুরেন্ট")
plans = superadmin_page("superadmin/plans.html", "প্ল্যান")
payments = superadmin_page("superadmin/payments.html", "পেমেন্ট")
