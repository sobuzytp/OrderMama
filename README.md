# OrderMama

Multi-tenant QR restaurant ordering SaaS built with **Django + HTML/CSS/vanilla JavaScript**.
Many restaurants share one installation; each has its own menu, tables, staff and orders.

## Features

| Area | What it does |
|------|--------------|
| QR tables | Each table has an unguessable token. QR links look like `/r/<slug>/t/<token>/`, so the table is detected automatically and cannot be swapped by editing a number. Older `/r/<slug>/table/<n>/` links keep working. |
| Menu & stock | Owner adds/edits items and price, and flips **In stock / Out of stock** instantly. Sold-out items show "স্টক শেষ" and cannot be ordered. |
| Cooking notes | Customers write a note per item ("Less spicy"); it appears on the KOT ticket. |
| Live KOT | Kitchen/cashier screen updates itself and plays a **sound alert** for new orders and waiter/bill calls. |
| Order tracking | Customers see Pending → Accepted → Cooking → Ready → Served update live, and can call a waiter or ask for the bill. |
| Super Admin (`/control/`) | Creates restaurants + owner logins, sees plans/expiry, gets expiry warnings, verifies bKash/Nagad payments. |
| Subscriptions | Plans (price, days, table/menu-item limits), subscriptions with grace days, manual bKash/Nagad payment records with future API fields. |

URLs: `/` · `/demo/` · `/r/<slug>/t/<token>/` · `/r/<slug>/track/<token>/` · `/dashboard/<slug>/` · `/dashboard/<slug>/kot/` · `/dashboard/<slug>/manage/` · `/dashboard/<slug>/billing/` · `/control/` · `/admin/`

## Local setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py test
python manage.py createsuperuser      # becomes the Super Admin (is_staff)
python manage.py runserver
```

## Database: SQLite now, PostgreSQL later (no code changes)

`config/settings.py` reads `DATABASE_URL` through `python-decouple` + `dj-database-url`.

* `DATABASE_URL` empty → `db.sqlite3`
* `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/NAME` → PostgreSQL

Switching: create the PostgreSQL database, set `DATABASE_URL` in `.env`, run `python manage.py migrate`.
Switching does **not** copy existing SQLite data. To keep it, export first
(`python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission > data.json`),
switch, migrate, then `python manage.py loaddata data.json`. Always back up before migrating live data.

## Real-time on cPanel

cPanel (Passenger) serves WSGI only, so WebSockets do not work there. The kitchen screen therefore
**polls `/dashboard/<slug>/live.json` every `LIVE_POLL_SECONDS` (default 5)** — this works everywhere.
If the server also supports WebSockets (ASGI + `/ws/orders/<slug>/`), the screen uses them and slows
polling to a 30 s safety net. Browsers only allow sounds after a click, so staff press
**"শব্দ চালু করুন"** once per device.

## Subscriptions and payments (manual bKash / Nagad)

1. In `/admin/` create **Plans** (price, duration, optional limits).
2. Set `PAYMENT_BKASH_NUMBER` / `PAYMENT_NAGAD_NUMBER` in `.env`.
3. The owner opens **Plan & billing**, sends money, and submits the Transaction ID.
4. Super Admin checks the SMS on `/control/` and clicks **Verify** → the subscription starts or is extended.
5. Duplicate Transaction IDs are rejected (a rejected ID may be resubmitted).
6. `ENFORCE_SUBSCRIPTIONS=1` stops ordering for restaurants without a valid (or grace-period) subscription. It is off by default so existing restaurants keep working.
7. Expiry e-mails: schedule a daily cPanel cron job:
   `/path/to/venv/bin/python /path/to/manage.py check_subscriptions`

The `PaymentTransaction.gateway_payment_id` / `gateway_payload` fields are reserved for a future automatic API integration.

## Deploying to cPanel

1. Pull/upload the code; create a Python App pointing at `passenger_wsgi.py`.
2. `pip install -r requirements.txt`, create `.env` with `DEBUG=0`, a real `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL`.
3. `python manage.py migrate && python manage.py collectstatic --noinput`, then restart the app (`tmp/restart.txt`).
4. Uploaded images (`media/`) need a web-server alias to `MEDIA_ROOT`; they are not served by Django in production.

## Checks

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --check
python manage.py check --deploy
python manage.py test
```

## Not done yet

Automatic bKash/Nagad API payments, subdomain routing (the `Restaurant.subdomain` field is ready), rate limiting,
monitoring and backup automation. Complete a security review and tenant-isolation test before taking real orders.
