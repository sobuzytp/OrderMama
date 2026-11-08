"""ডেমো ডেটা: প্ল্যান, দুটি রেস্টুরেন্ট (প্রিমিয়াম ও বেসিক), স্টাফ, মেনু, টেবিল, সুপার অ্যাডমিন।
শুধু ডেভেলপমেন্টের জন্য — প্রোডাকশনে চালাবেন না।"""
import io
from datetime import timedelta

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from PIL import Image, ImageDraw

from apps.accounts.models import User
from apps.menu.models import Category, MenuItem
from apps.restaurants.models import Restaurant, Table
from apps.subscriptions.models import Plan, Subscription

MENU = {
    "বিরিয়ানি": [
        ("কাচ্চি বিরিয়ানি", "খাসির মাংস, আতপ চাল, আলুবোখারা", 380, False, "#C8741A"),
        ("মুরগির তেহারি", "সরিষার তেলে রান্না, ঝাল-ঝাল", 220, False, "#D98E2B"),
        ("মাশরুম পোলাও", "ঘি-য়ে ভাজা মাশরুম ও কাজুবাদাম", 260, True, "#A8892B"),
    ],
    "কাবাব ও গ্রিল": [
        ("শিক কাবাব (৪ পিস)", "কয়লায় ঝলসানো গরুর কিমা", 240, False, "#9C3B1B"),
        ("চিকেন টিক্কা", "দইয়ের মশলায় মেরিনেট করা", 280, False, "#B5481F"),
        ("পনির টিক্কা", "তন্দুরে সেঁকা, পুদিনার চাটনি", 250, True, "#C9622A"),
    ],
    "ড্রিংকস": [
        ("বোরহানি", "ঘরে বানানো, পুদিনা-টক", 60, True, "#4C7A3C"),
        ("লাচ্ছি", "মিষ্টি দইয়ের লাচ্ছি", 90, True, "#C9A227"),
        ("কোল্ড কফি", "বরফ ও ক্রিমসহ", 130, True, "#6B4A32"),
    ],
    "মিষ্টি": [
        ("ফিরনি", "মাটির বাটিতে", 80, True, "#D8B77A"),
        ("গুলাব জামুন (২ পিস)", "গরম পরিবেশন", 70, True, "#7A3B1E"),
    ],
}


def plate(color, size=720):
    img = Image.new("RGB", (size, size), color)
    d = ImageDraw.Draw(img)
    for i in range(size):  # ওপর থেকে নিচে হালকা গাঢ়
        d.line([(0, i), (size, i)], fill=tuple(max(0, int(c * (1 - i / size * 0.35))) for c in img.getpixel((0, 0))))
    m = size * 0.16
    d.ellipse([m, m, size - m, size - m], fill=(250, 246, 238))
    m2 = size * 0.27
    d.ellipse([m2, m2, size - m2, size - m2], fill=color)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=80)
    return ContentFile(buf.getvalue())


class Command(BaseCommand):
    help = "ডেমো ডেটা তৈরি (DEBUG=True হলে)"

    def handle(self, *args, **opts):
        if not settings.DEBUG:
            raise CommandError("প্রোডাকশনে ডেমো ডেটা চালানো যাবে না (DJANGO_DEBUG=True লাগবে)।")
        call_command("seed_plans")
        premium, basic = Plan.objects.get(code="premium"), Plan.objects.get(code="basic")
        for slug, name, plan, color in [
            ("demo-biryani", "দাওয়াত বিরিয়ানি হাউস", premium, "#B5121B"),
            ("demo-basic", "সকালের নাশতা ঘর", basic, "#E85D04"),
        ]:
            r, _ = Restaurant.objects.get_or_create(slug=slug, defaults=dict(
                name=name, phone="01712345678", address="ধানমন্ডি, ঢাকা", is_approved=True,
                primary_color=color, secondary_color="#FFF6EC", vat_percent=5, service_charge_percent=10,
            ))
            Subscription.objects.update_or_create(restaurant=r, defaults=dict(
                plan=plan, end_date=timezone.now() + timedelta(days=30)))
            for n in range(1, 9):
                Table.objects.get_or_create(restaurant=r, number=n)
            if not r.categories.exists():
                for pos, (cname, items) in enumerate(MENU.items()):
                    cat = Category.objects.create(restaurant=r, name=cname, position=pos)
                    for ipos, (iname, desc, price, veg, colr) in enumerate(items):
                        it = MenuItem(restaurant=r, category=cat, name=iname, description=desc,
                                      price=price, is_veg=veg, position=ipos)
                        it.image.save(f"{slug}-{pos}-{ipos}.webp", plate(colr), save=False)
                        it.save()
                MenuItem.objects.filter(restaurant=r, name="চিকেন টিক্কা").update(is_stock_out=True)
            for role in ["owner", "manager", "cashier", "kitchen", "waiter"]:
                u, created = User.objects.get_or_create(
                    username=f"{slug.split('-')[1]}_{role}", defaults=dict(restaurant=r, role=role))
                if created:
                    u.set_password("demo12345")
                    u.save()
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", password="admin12345")
        self.stdout.write(self.style.SUCCESS("ডেমো প্রস্তুত।"))
        self.stdout.write("কাস্টমার লিংক (QR-এ যা থাকে):")
        for t in Table.objects.filter(restaurant__slug__startswith="demo-", number__in=[1, 3]).select_related("restaurant"):
            self.stdout.write(f"  {settings.SITE_BASE_URL}/{t.restaurant.slug}/{t.token}/   ({t.restaurant.name}, {t.display_name})")
        self.stdout.write("স্টাফ: biryani_owner / biryani_manager / biryani_cashier / biryani_kitchen / biryani_waiter (পাসওয়ার্ড demo12345)")
        self.stdout.write("সুপার অ্যাডমিন: admin / admin12345")
