# OrderMama

OrderMama is a Django-based QR restaurant ordering platform under active development.

## Technology direction

- Backend: Django
- Frontend: Django Templates with HTML, CSS and vanilla JavaScript
- Development database: SQLite
- Production database: PostgreSQL
- Optional real-time delivery: Django Channels with Redis

The customer, restaurant staff and platform administration screens will use the same Django application and role/restaurant-scoped views. A separate React application is not part of the current implementation plan.

## Requirements

- Python 3.11+
- PostgreSQL for production (SQLite is used by default for local development)
- Redis recommended when running multiple application processes and using WebSockets

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

With `DATABASE_URL` empty or unset, Django uses the local `db.sqlite3` file. This is suitable for development and testing.

## PostgreSQL for production

Set `DATABASE_URL` in the hosting environment or private `.env` file:

```text
DATABASE_URL=postgresql://DB_USER:DB_PASSWORD@DB_HOST:5432/DB_NAME
DEBUG=0
ALLOWED_HOSTS=your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com
```

Use the actual database name, username, password and host provided by your hosting company. Never commit `.env` or share database credentials. Install dependencies from `requirements.txt`, then run migrations after switching the production environment to PostgreSQL. Keep a verified backup before migrating existing live data; changing the database URL does not copy SQLite data into PostgreSQL.

## Customer experience

- Home page: `/`
- Sample customer demo: `/demo/` (demonstration only; it does not create a real order or accept payment)
- Live restaurant menu: `/r/<slug>/table/<number>/`
- Order tracking: `/r/<slug>/track/<token>/`
- Restaurant staff dashboard: `/dashboard/<slug>/`
- Kitchen order view: `/dashboard/<slug>/kot/`
- Super Admin portal: `/control/`

Create a Restaurant, DiningTable, Category, MenuItem and RestaurantMembership in Django admin. Add a membership with role `owner` for the restaurant owner.

## Current implementation boundaries

- Restaurant staff HTML views are scoped to the selected restaurant and role. The WebSocket order stream requires authenticated restaurant staff.
- Customer order totals are recalculated from current database prices; cart item IDs must belong to the same restaurant and an active category.
- Subscription records and grace-period calculation exist, but plan enforcement, checkout, renewals, invoices, and payment webhooks are not implemented.
- Django REST Framework is currently installed but a documented public/staff API is not yet implemented; the current frontend is Django Templates, HTML, CSS and JavaScript.
- Payment processing is deliberately disabled. Before integrating a provider, add signature-verified idempotent webhooks, transaction records, reconciliation, and provider credentials stored as secrets.
- Restaurant onboarding, full menu/table CRUD screens, rate limiting, monitoring, backups, and production deployment automation remain follow-up work.
- The project is not yet production-certified. Complete security review, database backup/restore testing, tenant-isolation testing and deployment checks before accepting real restaurant orders.

## Checks

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python manage.py check --deploy
python manage.py test
```
