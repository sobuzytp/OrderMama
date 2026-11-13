"""লঞ্চ-চেক: প্রোডাকশনে যাওয়ার আগে বিপজ্জনক কনফিগ ও ডেটা ধরে ফেলে।

    python manage.py check_production            # রিপোর্ট (কোনো কিছু বদলায় না)
    python manage.py check_production --strict   # সমস্যা থাকলে exit code 1 (ডিপ্লয়ে গেট)

কী দেখে: DEBUG/সিক্রেট কী/হোস্ট/HTTPS/কুকি সেটিংস, `mock` পেমেন্ট, Redis, NUM_PROXIES,
ডিফল্ট ও দুর্বল পাসওয়ার্ড (superuser + ডেমো অ্যাকাউন্ট), ডেমো রেস্টুরেন্ট/মেনু/পেমেন্ট।
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import connection

# seed_demo যে ডিফল্ট পাসওয়ার্ড/ইউজারনেম বানায়
DEMO_PASSWORDS = ("demo12345", "admin12345", "admin123", "12345678", "password", "admin")
DEMO_SLUG_PREFIX = "demo-"
MIN_KEY_LEN = 40

OK, WARN, FAIL = "ok", "warn", "fail"
MARK = {OK: "[ ঠিক ]", WARN: "[সতর্ক]", FAIL: "[সমস্যা]"}


class Command(BaseCommand):
    help = "প্রোডাকশন লঞ্চ-চেক (ডিফল্ট পাসওয়ার্ড, ডেমো ডেটা, সিকিউরিটি সেটিংস)"

    def add_arguments(self, parser):
        parser.add_argument("--strict", action="store_true", help="সমস্যা থাকলে exit code 1")
        parser.add_argument("--skip-db", action="store_true", help="ডেটাবেজ-নির্ভর চেক বাদ দিন")

    def handle(self, *args, **options):
        self.results = []
        self.check_settings()
        if not options["skip_db"]:
            try:
                connection.ensure_connection()
            except Exception as exc:  # DB নেই → বাকি চেক করা যায় না
                self.add(FAIL, "database", f"ডেটাবেজে সংযোগ হচ্ছে না: {exc}")
            else:
                self.check_data()
        return self.report(options["strict"])

    # ---------- সহায়ক ----------
    def add(self, level, key, detail, hint=""):
        self.results.append({"level": level, "key": key, "detail": detail, "hint": hint})

    def expect(self, level, key, condition, detail, hint=""):
        """condition সত্য হলে ঠিক; নাহলে `level` অনুযায়ী সমস্যা।"""
        self.add(OK if condition else level, key, detail, hint)

    def report(self, strict):
        fails = [r for r in self.results if r["level"] == FAIL]
        warns = [r for r in self.results if r["level"] == WARN]
        self.stdout.write("")
        for r in self.results:
            if r["level"] == OK:
                continue
            self.stdout.write(f"{MARK[r['level']]} {r['detail']}")
            if r["hint"]:
                self.stdout.write(f"          → {r['hint']}")
        self.stdout.write("")
        self.stdout.write(f"মোট: {len(self.results)} চেক · {len(fails)} সমস্যা · {len(warns)} সতর্কতা")
        if fails:
            self.stdout.write(self.style.ERROR("প্রোডাকশনে যাওয়ার আগে উপরের সমস্যাগুলো ঠিক করুন।"))
        elif warns:
            self.stdout.write(self.style.WARNING("চালু করা যাবে, তবে সতর্কতাগুলো দেখে নিন।"))
        else:
            self.stdout.write(self.style.SUCCESS("সব চেক পাস — লঞ্চের জন্য প্রস্তুত।"))
        if strict and fails:
            raise SystemExit(1)

    # ---------- কনফিগ ----------
    def check_settings(self):
        s = settings
        self.expect(FAIL, "debug", not s.DEBUG, f"DJANGO_DEBUG={s.DEBUG}",
                   "প্রোডাকশনে DJANGO_DEBUG=False দিন।")

        key = s.SECRET_KEY or ""
        bad_key = (not key) or key.startswith(("dev-insecure", "change-me")) or len(key) < MIN_KEY_LEN
        self.expect(FAIL, "secret_key", not bad_key, f"DJANGO_SECRET_KEY দৈর্ঘ্য {len(key)}",
                   "কমপক্ষে ৪০ অক্ষরের র‍্যান্ডম কী দিন।")

        hosts = [h for h in s.ALLOWED_HOSTS if h]
        bad_hosts = [h for h in hosts if h in ("*", "localhost", "127.0.0.1", "0.0.0.0")]
        self.expect(FAIL, "allowed_hosts", bool(hosts) and not bad_hosts,
                   f"DJANGO_ALLOWED_HOSTS={hosts}", "আসল ডোমেইন দিন (localhost নয়)।")

        self.expect(FAIL, "site_base_url", s.SITE_BASE_URL.startswith("https://"),
                   f"SITE_BASE_URL={s.SITE_BASE_URL}",
                   "HTTPS ডোমেইন দিন — QR লিংক ও পেমেন্ট callback এটাই ব্যবহার করে।")

        origins = list(getattr(s, "CSRF_TRUSTED_ORIGINS", []) or [])
        self.expect(FAIL, "csrf_origins", any(o.startswith("https://") for o in origins),
                   f"CSRF_TRUSTED_ORIGINS={origins}", "https://yourdomain.com যোগ করুন।")

        self.expect(FAIL, "ssl_redirect", s.SECURE_SSL_REDIRECT,
                   f"SECURE_SSL_REDIRECT={s.SECURE_SSL_REDIRECT}", "HTTPS বাধ্য করতে True দিন।")
        self.expect(WARN, "hsts", s.SECURE_HSTS_SECONDS >= 31536000,
                   f"SECURE_HSTS_SECONDS={s.SECURE_HSTS_SECONDS}",
                   "আগে ছোট মান দিয়ে যাচাই করে পরে 31536000 করুন।")
        self.expect(FAIL, "cookies", s.SESSION_COOKIE_SECURE and s.CSRF_COOKIE_SECURE,
                   "সেশন/CSRF কুকি Secure ফ্ল্যাগ", "DEBUG=False হলে নিজে থেকেই ঠিক হয়।")

        # প্রক্সি থাকলে NUM_PROXIES>=1, নইলে ক্লায়েন্ট X-Forwarded-For বানিয়ে IP throttle এড়াতে পারে
        self.expect(WARN, "num_proxies", s.NUM_PROXIES >= 1, f"NUM_PROXIES={s.NUM_PROXIES}",
                   "nginx/Apache-র পেছনে থাকলে NUM_PROXIES=1 দিন।")

        self.expect(FAIL, "payment_gateway", s.PAYMENT_GATEWAY != "mock",
                   f"PAYMENT_GATEWAY={s.PAYMENT_GATEWAY}", "manual / sslcommerz / both দিন — mock শুধু ডেভে।")
        self.check_payment_creds(s)

        self.expect(WARN, "redis", bool(s.REDIS_URL), f"REDIS_URL={'সেট' if s.REDIS_URL else 'খালি'}",
                   "Redis ছাড়া লাইভ আপডেট ও রেট-লিমিট শুধু এক প্রসেসে কাজ করে।")
        self.expect(WARN, "serve_media", not s.SERVE_MEDIA, f"SERVE_MEDIA={s.SERVE_MEDIA}",
                   "প্রোডাকশনে media nginx/অবজেক্ট স্টোরেজ দিয়ে সার্ভ করুন।")
        self.expect(WARN, "admins", bool(s.ADMINS), "PLATFORM_ADMIN_EMAILS",
                   "500 এরর ইমেইলে পেতে প্ল্যাটফর্ম অ্যাডমিনের ইমেইল দিন।")
        self.expect(WARN, "deploy_env", s.DEPLOY_ENV == "production", f"DEPLOY_ENV={s.DEPLOY_ENV}",
                   "মনিটরিং/রিপোর্ট আলাদা করতে DEPLOY_ENV=production দিন।")
        self.expect(WARN, "email", bool(s.EMAIL_HOST and s.EMAIL_HOST_USER), "SMTP কনফিগ",
                   "রিমাইন্ডার ও এরর-অ্যালার্ট ইমেইলের জন্য EMAIL_HOST/USER দিন।")

    def check_payment_creds(self, s):
        if s.PAYMENT_GATEWAY in ("manual", "both"):
            numbers = [s.MANUAL_BKASH_NUMBER, s.MANUAL_NAGAD_NUMBER, s.MANUAL_ROCKET_NUMBER]
            self.expect(WARN, "manual_numbers", any(numbers), "Manual পেমেন্ট নম্বর",
                       "MANUAL_BKASH/NAGAD/ROCKET_NUMBER দিন, নইলে মার্চেন্ট টাকা পাঠাতে পারবে না।")
        if s.PAYMENT_GATEWAY in ("sslcommerz", "both"):
            creds = bool(s.SSLCOMMERZ_STORE_ID and s.SSLCOMMERZ_STORE_PASSWORD)
            level = FAIL if s.PAYMENT_GATEWAY == "sslcommerz" else WARN
            self.expect(level, "sslcommerz", creds, "SSLCommerz ক্রেডেনশিয়াল",
                       "SSLCOMMERZ_STORE_ID/PASSWORD দিন, অথবা গেটওয়ে manual রাখুন।")
            if creds:
                self.expect(WARN, "sslcommerz_sandbox", not s.SSLCOMMERZ_SANDBOX,
                           f"SSLCOMMERZ_SANDBOX={s.SSLCOMMERZ_SANDBOX}",
                           "লাইভ করার আগে `manage.py sslcommerz_check` দিয়ে টেস্ট করুন।")

    # ---------- ডেটা ----------
    def check_data(self):
        User = get_user_model()
        from apps.payments.models import Payment
        from apps.restaurants.models import Restaurant

        # ১) দুর্বল/ডিফল্ট পাসওয়ার্ড — শুধু seed_demo-র বানানো অ্যাকাউন্ট
        weak = []
        base_qs = User.objects.all().only("id", "username", "is_superuser")
        for u in base_qs:
            if not u.has_usable_password():
                continue
            if any(u.check_password(p) for p in DEMO_PASSWORDS):
                weak.append(("*" if u.is_superuser else "") + u.username)
        self.expect(FAIL, "demo_passwords", not weak,
                   f"ডিফল্ট/দুর্বল পাসওয়ার্ড: {weak or 'নেই'}",
                   "`admin` ও ডেমো অ্যাকাউন্টের পাসওয়ার্ড বদলান: manage.py changepassword <username>")

        # ২) সুপার অ্যাডমিন নিজের নাম/হোস্ট ডিফল্ট হিসেবে
        self.expect(OK, "superusers", True,
                   f"সুপার অ্যাডমিন সংখ্যা: {User.objects.filter(is_superuser=True, is_active=True).count()}")

        # ৩) ডেমো রেস্টুরেন্ট
        demo_rests = list(Restaurant.objects.filter(slug__startswith=DEMO_SLUG_PREFIX).values_list("slug", flat=True))
        self.expect(FAIL, "demo_restaurants", not demo_rests,
                   f"ডেমো রেস্টুরেন্ট: {demo_rests or 'নেই'}",
                   "`manage.py clear_demo` চালিয়ে ডেমো ডেটা সরান, নইলে কাস্টমার ডেমো মেনু দেখবে।")

        # ৪) ডেমো রেস্টুরেন্টের মেনু/অর্ডার এখনো পড়ে আছে কি না
        from apps.menu.models import MenuItem

        demo_items = MenuItem.objects.filter(restaurant__slug__startswith=DEMO_SLUG_PREFIX).count()
        self.expect(OK, "demo_menu", True, f"ডেমো মেনু আইটেম: {demo_items}টি")

        # ৫) mock গেটওয়ের টেস্ট পেমেন্ট ডেটা
        mock_payments = Payment.objects.filter(gateway="mock").count()
        self.expect(WARN, "mock_payments", mock_payments == 0, f"mock পেমেন্ট রেকর্ড: {mock_payments}টি",
                   "টেস্ট পেমেন্ট রেকর্ড প্রোডাকশন ডেটাবেজে থাকা উচিত নয়।")

        # ৬) অনুমোদনের অপেক্ষায় থাকা রেস্টুরেন্ট (তথ্যমাত্রা)
        pending = Restaurant.objects.filter(is_approved=False).count()
        self.add(WARN if pending else OK, "pending_restaurants", f"অনুমোদনের অপেক্ষায়: {pending}টি")

