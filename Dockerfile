FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=config.settings

# ফন্ট: QR PDF-এ বাংলা লেখার জন্য (FreeSans); libraqm: Pillow-র টেক্সট শেপিং
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-freefont-ttf fonts-noto-core libraqm0 curl \
    && rm -rf /var/lib/apt/lists/*

# non-root ব্যবহারকারী (কনটেইনার ফাঁক হলে ক্ষতি কম)
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# এন্ট্রিপয়েন্ট: migrate → (চাইলে) check_production → daphne
COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh
RUN mkdir -p /app/staticfiles /app/media /app/logs /app/backups \
    && chown -R app:app /app \
    && DJANGO_SECRET_KEY=build DJANGO_DEBUG=False python manage.py collectstatic --noinput

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/healthz/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]

