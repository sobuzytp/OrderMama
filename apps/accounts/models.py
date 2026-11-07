from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = "owner", "ওনার"
        MANAGER = "manager", "ম্যানেজার"
        CASHIER = "cashier", "ক্যাশিয়ার"
        KITCHEN = "kitchen", "কিচেন স্টাফ"
        WAITER = "waiter", "ওয়েটার"

    # রেস্টুরেন্ট-স্টাফের জন্য। সুপার অ্যাডমিনের restaurant খালি থাকে।
    restaurant = models.ForeignKey(
        "restaurants.Restaurant",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="staff",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_platform_admin(self):
        return self.is_active and self.is_superuser

    @property
    def is_restaurant_manager(self):
        return self.role in (self.Role.OWNER, self.Role.MANAGER)
