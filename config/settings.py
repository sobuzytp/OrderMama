"""OrderMama settings. সব গোপন তথ্য .env ফাইল থেকে আসে।"""
import os
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return config(name, default=default, cast=bool)


def env_list(name, default=""):
    return config(name, default=default, cast=Csv())


DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = config("DJANGO_SECRET_KEY", default="")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-insecure-key-do-not-use-in-production"
    else:
        raise RuntimeError("DJANGO_SECRET_KEY সেট করা নেই (.env দেখুন)।")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "apps.accounts",
    "apps.restaurants",
    "apps.menu",
    "apps.orders",
    "apps.subscriptions",
    "apps.payments",
    "apps.realtime",
    "apps.analytics",
    "apps.web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ডেটাবেজ: DATABASE_URL থাকলে PostgreSQL, না থাকলে ডেভের জন্য SQLite
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}", conn_max_age=600
    )
}

# ক্যাশ (রেট-লিমিটের কাউন্টার): প্রোডাকশনে একাধিক ওয়ার্কারের জন্য Redis
if config("REDIS_URL", default=""):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": config("REDIS_URL"),
        }
    }

# Channels: REDIS_URL থাকলে Redis, না থাকলে In-Memory (শুধু ডেভ)
REDIS_URL = config("REDIS_URL", default="")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/merchant/login/"
LOGIN_REDIRECT_URL = "/merchant/dashboard/"
LOGOUT_REDIRECT_URL = "/merchant/login/"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "bn"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {
        "customer_order": "10/min",
        "customer_call": "6/min",
        "customer_session": "30/min",
        "customer_ip": "90/min",
        "register": "5/hour",
    },
}

# ব্যবসায়িক সেটিংস
SITE_BASE_URL = config("SITE_BASE_URL", default="http://localhost:8000").rstrip("/")
TABLE_SESSION_MAX_AGE = 60 * 60 * 6  # ৬ ঘণ্টা
SUBSCRIPTION_WARNING_DAYS = 3

PAYMENT_GATEWAY = config("PAYMENT_GATEWAY", default="mock")
SSLCOMMERZ_STORE_ID = config("SSLCOMMERZ_STORE_ID", default="")
SSLCOMMERZ_STORE_PASSWORD = config("SSLCOMMERZ_STORE_PASSWORD", default="")
SSLCOMMERZ_SANDBOX = env_bool("SSLCOMMERZ_SANDBOX", True)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
