"""
OrderMama settings.

All environment-specific values come from a `.env` file (or real environment
variables) read through python-decouple. Nothing secret lives in this file.

Database switching
------------------
* `DATABASE_URL` empty / missing  -> local SQLite file (`db.sqlite3`)
* `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/NAME` -> PostgreSQL

No application code changes are needed when you switch; only `.env` changes.
"""
from pathlib import Path

import dj_database_url
from decouple import Csv, config

BASE_DIR = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY", default="django-insecure-local-development-only")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())
CSRF_TRUSTED_ORIGINS = config("CSRF_TRUSTED_ORIGINS", default="", cast=Csv())
# Public base URL used inside QR codes and e-mails (no trailing slash).
SITE_URL = config("SITE_URL", default="http://127.0.0.1:8000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "core.apps.CoreConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# --------------------------------------------------------------------------
# Database: PostgreSQL when DATABASE_URL is set, otherwise SQLite.
# --------------------------------------------------------------------------
DATABASE_URL = config("DATABASE_URL", default="").strip()

if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=config("DB_CONN_MAX_AGE", default=600, cast=int),
            ssl_require=config("DATABASE_SSL_REQUIRE", default=False, cast=bool),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# --------------------------------------------------------------------------
# Localisation, static and media files
# --------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Dhaka"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/login/"

# --------------------------------------------------------------------------
# Real-time: WebSocket (Channels) with automatic polling fallback.
# cPanel/Passenger cannot serve WebSockets, so the KOT screen polls as well.
# --------------------------------------------------------------------------
REDIS_URL = config("REDIS_URL", default="")
CHANNEL_LAYERS = {"default": {
    "BACKEND": "channels_redis.core.RedisChannelLayer",
    "CONFIG": {"hosts": [REDIS_URL]},
}} if REDIS_URL else {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
LIVE_POLL_SECONDS = config("LIVE_POLL_SECONDS", default=5, cast=int)

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
}

# --------------------------------------------------------------------------
# Subscriptions & manual bKash / Nagad payments
# --------------------------------------------------------------------------
# While False, restaurants without a subscription keep working (safe default
# for existing live data). Set ENFORCE_SUBSCRIPTIONS=1 once plans are in place.
ENFORCE_SUBSCRIPTIONS = config("ENFORCE_SUBSCRIPTIONS", default=False, cast=bool)
SUBSCRIPTION_ALERT_DAYS = config("SUBSCRIPTION_ALERT_DAYS", default=7, cast=int)
PAYMENT_BKASH_NUMBER = config("PAYMENT_BKASH_NUMBER", default="")
PAYMENT_NAGAD_NUMBER = config("PAYMENT_NAGAD_NUMBER", default="")

EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="localhost")
EMAIL_PORT = config("EMAIL_PORT", default=25, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=False, cast=bool)
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="OrderMama <no-reply@localhost>")

# --------------------------------------------------------------------------
# Security
# --------------------------------------------------------------------------
SECURE_SSL_REDIRECT = not DEBUG and config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = config("SECURE_HSTS_SECONDS", default=0 if DEBUG else 31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
