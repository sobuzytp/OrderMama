#!/bin/sh
# OrderMama কনটেইনার এন্ট্রিপয়েন্ট — migrate → (ঐচ্ছিক) প্রোডাকশন চেক → অ্যাপ
# কমান্ড ওভাররাইড করা যায়: docker compose run --rm web python manage.py check_production
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] migrate…"
  python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-0}" = "1" ]; then
  echo "[entrypoint] collectstatic…"
  python manage.py collectstatic --noinput
fi

# STRICT_BOOT=1 হলে ডিফল্ট পাসওয়ার্ড/ডেমো ডেটা থাকলে অ্যাপই চালু হবে না
if [ "${STRICT_BOOT:-0}" = "1" ]; then
  echo "[entrypoint] প্রোডাকশন চেক (STRICT_BOOT=1)…"
  python manage.py check_production --strict
fi

echo "[entrypoint] চালু: $*"
exec "$@"
