# OrderMama

Django-based QR restaurant ordering starter (not yet a production-certified SaaS).

## Requirements
- Python 3.11+
- PostgreSQL in production (SQLite is supported for local development)
- Redis recommended for multi-process WebSocket delivery

## Local setup
```bash
python -m venv .venv
# Activate the environment
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py check
python manage.py test
python manage.py createsuperuser
python manage.py runserver
```

Create a Restaurant, DiningTable, Category, MenuItem and RestaurantMembership in Django admin. Add a membership with role `owner` for the restaurant owner. Customer menu: `/r/<slug>/table/<number>/`; staff dashboard: `/dashboard/<slug>/`; kitchen view: `/dashboard/<slug>/kot/`.

## Environment
Set a unique random `SECRET_KEY`, `DEBUG=0`, `ALLOWED_HOSTS`, `DATABASE_URL`, `SITE_URL`, `REDIS_URL`, and (if needed) `CSRF_TRUSTED_ORIGINS`. Terminate HTTPS at the proxy/load balancer. Do not expose Redis or PostgreSQL publicly. Run `python manage.py check --deploy` before release and resolve every warning. Keep secrets in the hosting provider's secret manager; never commit `.env`.

## Current implementation boundaries
- Staff HTML views are scoped to the selected restaurant and role. The WebSocket order stream requires authenticated restaurant staff.
- Customer order totals are recalculated from current database prices; cart item IDs must belong to the same restaurant and an active category.
- Subscription records and grace-period calculation exist, but plan enforcement, checkout, renewals, invoices, and payment webhooks are not implemented.
- DRF is installed but a documented public/staff API is not yet implemented.
- Payment processing is deliberately disabled. Before integrating a provider, add signature-verified idempotent webhooks, transaction records, reconciliation, and provider credentials stored as secrets. Never trust a browser redirect as proof of payment.
- Restaurant onboarding, full menu/table CRUD screens, rate limiting, monitoring, backups, and production deployment automation remain follow-up work.

## Checks
`python manage.py makemigrations --check --dry-run`
`python manage.py migrate --check`
`python manage.py check --deploy`
`python manage.py test`
