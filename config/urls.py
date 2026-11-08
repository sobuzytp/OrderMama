from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("payments/", include("apps.payments.urls")),
    path("api/", include("apps.web.api_urls")),
    path("", include("apps.web.urls")),
]
if settings.SERVE_MEDIA:  # cPanel/Passenger-এ nginx ছাড়া ছবি সার্ভ করতে (.env: SERVE_MEDIA=True)
    urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]
elif settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
