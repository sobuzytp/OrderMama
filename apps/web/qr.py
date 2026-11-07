"""টেবিলের প্রিন্ট-রেডি QR PDF (প্রতি টেবিলে একটি A5 পৃষ্ঠা)।

বাংলা লেখার জন্য ReportLab-এ জটিল-অক্ষরের শেপিং নেই, তাই লেখা Pillow (raqm) দিয়ে ছবি করে বসানো হয়।
ফন্টের খোঁজ: QR_FONT_PATH → static/fonts/*.ttf → সিস্টেমের Noto Sans Bengali → FreeSans।
"""
import glob
import io
import os

import qrcode
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_M
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A5
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/lohit-bengali/Lohit-Bengali.ttf",
]


def _font_path():
    env = os.getenv("QR_FONT_PATH")
    if env and os.path.exists(env):
        return env
    local = sorted(glob.glob(str(settings.BASE_DIR / "static" / "fonts" / "*.ttf")))
    for p in local + _FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def text_image(text, px, color="#222222", max_width=None):
    """লেখাকে স্বচ্ছ ব্যাকগ্রাউন্ডের ছবিতে আঁকে; বড় হলে ফন্ট ছোট করে।"""
    path = _font_path()
    if not path:
        font = ImageFont.load_default()
    else:
        while True:
            try:
                font = ImageFont.truetype(path, px, layout_engine=ImageFont.Layout.RAQM)
            except Exception:
                font = ImageFont.truetype(path, px)
            w = font.getbbox(text)[2]
            if not max_width or w <= max_width or px <= 20:
                break
            px = int(px * 0.9)
    l, t, r, b = font.getbbox(text)
    img = Image.new("RGBA", (r + 8, b + 12), (0, 0, 0, 0))
    ImageDraw.Draw(img).text((2, 2), text, font=font, fill=color)
    return img


def _qr_image(url, color):
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=12, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color=color, back_color="white").convert("RGB")


def _draw_text(c, text, cx, y, px, color, max_w_pt):
    img = text_image(text, px, color, max_width=int(max_w_pt * 4))
    w = img.width / 4  # ৪ গুণ রেজুলেশনে আঁকা
    h = img.height / 4
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    c.drawImage(ImageReader(buf), cx - w / 2, y, width=w, height=h, mask="auto")


def build_qr_pdf(restaurant, tables):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A5)
    W, H = A5
    accent = restaurant.primary_color if restaurant.has_feature("branding") else "#E85D04"
    for t in tables:
        url = f"{settings.SITE_BASE_URL}/{restaurant.slug}/{t.token}/"
        # ওপরের রঙিন পটি
        c.setFillColor(HexColor(accent))
        c.rect(0, H - 120, W, 120, stroke=0, fill=1)
        _draw_text(c, restaurant.name, W / 2, H - 78, 112, "#FFFFFF", W - 60)
        # QR
        size = 250
        c.setFillColor(HexColor("#FFFFFF"))
        c.roundRect(W / 2 - size / 2 - 14, H - 120 - size - 50, size + 28, size + 28, 14, stroke=1, fill=1)
        c.drawImage(ImageReader(_qr_image(url, "#1A1A1A")), W / 2 - size / 2, H - 120 - size - 36,
                    width=size, height=size)
        # টেবিল নম্বর ও নির্দেশনা
        _draw_text(c, t.display_name, W / 2, 110, 140, accent, W - 60)
        _draw_text(c, "QR স্ক্যান করে অর্ডার করুন", W / 2, 66, 80, "#333333", W - 60)
        c.setFillColor(HexColor("#888888"))
        c.setFont("Helvetica", 8)
        c.drawCentredString(W / 2, 34, url)
        c.showPage()
    c.save()
    return buf.getvalue()
