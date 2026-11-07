from django.db import models

from apps.restaurants.models import Restaurant, validate_image_size


class Category(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField(max_length=80)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name_plural = "categories"

    def __str__(self):
        return f"{self.name} ({self.restaurant.name})"


class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="menu_items")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=300, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # আগের দাম (ডিসকাউন্ট ব্যাজের জন্য): price-এর চেয়ে বেশি হলে "-X%" ব্যাজ দেখায়
    compare_at_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to="menu/", blank=True, validators=[validate_image_size])
    is_veg = models.BooleanField(default=False)
    is_stock_out = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.name

    @property
    def discount_percent(self):
        if self.compare_at_price and self.compare_at_price > self.price:
            return int((self.compare_at_price - self.price) * 100 / self.compare_at_price)
        return 0

    def save(self, *args, **kwargs):
        # টেনান্ট নিরাপত্তা: আইটেমের restaurant সবসময় ক্যাটাগরির restaurant-এর সমান
        if self.category_id:
            self.restaurant_id = self.category.restaurant_id
        super().save(*args, **kwargs)
