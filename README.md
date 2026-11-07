# OrderMama
Multi-tenant QR restaurant ordering SaaS MVP. Stack: Django, DRF, PostgreSQL, Channels, Redis, HTML/CSS/Vanilla JS.

## Run locally
Python 3.11+, PostgreSQL (optional for local SQLite fallback).
```bash
python -m venv .venv
# activate the environment
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Create Restaurant, DiningTable, Category and MenuItem in /admin/. Add RestaurantMembership with role owner. Customer URL: /r/<slug>/table/<number>/. Dashboard: /dashboard/<slug>/.
Set DATABASE_URL, SECRET_KEY, ALLOWED_HOSTS, SITE_URL and REDIS_URL in production. Payment gateway credentials and webhook verification are intentionally not enabled; configure and audit before accepting money. Run tests with python manage.py test.
