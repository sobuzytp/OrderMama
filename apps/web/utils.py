import io
import os

from django.core.files.base import ContentFile
from rest_framework import serializers
from PIL import Image, UnidentifiedImageError

DEFAULT_PRIMARY = "#E85D04"
DEFAULT_SECONDARY = "#FFF8F0"


def compress_image(upload, max_side=1200, quality=82):
    """আপলোড করা ছবি যাচাই করে WEBP-তে কম্প্রেস করে। ছবি না হলে ValidationError।"""
    try:
        img = Image.open(upload)
        img.verify()
        upload.seek(0)
        img = Image.open(upload)
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise serializers.ValidationError("এটি সঠিক ছবি নয়। JPG, PNG বা WEBP দিন।")
    if img.format not in ("JPEG", "PNG", "WEBP"):
        raise serializers.ValidationError("শুধু JPG, PNG বা WEBP ছবি চলবে।")
    if img.width * img.height > 40_000_000:
        raise serializers.ValidationError("ছবিটি অতিরিক্ত বড়।")
    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=4)
    name = os.path.splitext(os.path.basename(upload.name))[0][:40] or "img"
    return ContentFile(buf.getvalue(), name=f"{name}.webp")


def brand_for(restaurant):
    """ব্র্যান্ডিং শুধু প্রিমিয়ামে; নইলে ডিফল্ট চেহারা।"""
    if restaurant.has_feature("branding"):
        return {
            "primary": restaurant.primary_color,
            "secondary": restaurant.secondary_color,
            "theme": restaurant.theme,
            "font": restaurant.font_style,
            "logo": restaurant.logo.url if restaurant.logo else "",
            "cover": restaurant.cover_image.url if restaurant.cover_image else "",
            "welcome": restaurant.welcome_message,
        }
    return {
        "primary": DEFAULT_PRIMARY,
        "secondary": DEFAULT_SECONDARY,
        "theme": "light",
        "font": "hind",
        "logo": "",
        "cover": "",
        "welcome": restaurant.welcome_message,
    }
