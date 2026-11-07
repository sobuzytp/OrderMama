from django.contrib.auth.views import LoginView
from django.urls import reverse
from .models import RestaurantMembership

class WorkspaceLoginView(LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.is_staff:
            return reverse("control")
        membership = RestaurantMembership.objects.filter(
            user=user, role__in=["owner", "manager", "cashier", "kitchen"]
        ).select_related("restaurant").first()
        if membership:
            return reverse("dashboard", kwargs={"slug": membership.restaurant.slug})
        return "/"
