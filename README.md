# OrderMama — রেস্টুরেন্ট QR অর্ডারিং SaaS

কাস্টমার টেবিলের QR স্ক্যান করে অর্ডার দেয় (লগইন ছাড়া), রেস্টুরেন্ট লাইভ KOT পায়, আর প্ল্যাটফর্ম মালিক সাবস্ক্রিপশন থেকে আয় করেন।

**স্ট্যাক:** Django · Django REST Framework · Django Channels (WebSocket) · SQLite/PostgreSQL · Redis · HTML/CSS/Vanilla JS

## রুট (লগইন-আইসোলেশন)
| পাথ | কে | লগইন |
|---|---|---|
| `/<restaurant-slug>/` | কাস্টমার — শুধু মেনু দেখা | না |
| `/<restaurant-slug>/<table-uuid>/` | কাস্টমার — QR-এর লিংক, অর্ডার করা যায় | না |
| `/merchant/…` | মালিক, ম্যানেজার, ক্যাশিয়ার, কিচেন, ওয়েটার | হ্যাঁ |
| `/super-admin/…` | প্ল্যাটফর্ম মালিক | হ্যাঁ (superuser) |
| `/register/` | নতুন রেস্টুরেন্ট আবেদন (অনুমোদনের অপেক্ষায় থাকে) | না |

## দ্রুত চালু (ডেভেলপমেন্ট)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # DATABASE_URL ও REDIS_URL খালি রাখলে SQLite + in-memory চলবে
python manage.py migrate
python manage.py seed_demo      # ডেমো রেস্টুরেন্ট, স্টাফ, মেনু (শুধু DEBUG=True তে)
daphne -b 127.0.0.1 -p 8000 config.asgi:application   # WebSocket-সহ চালানোর জন্য daphne লাগবে
```
`seed_demo` শেষে কাস্টমার QR-লিংক ও লগইন তথ্য ছাপে। ডেমো স্টাফ: `biryani_owner / biryani_cashier / biryani_kitchen …` (পাসওয়ার্ড `demo12345`), সুপার অ্যাডমিন `admin / admin12345` — **প্রোডাকশনে এগুলো কখনো রাখবেন না।**

## ডেটাবেজ: SQLite → PostgreSQL
`.env`-এ `DATABASE_URL` থাকলে PostgreSQL, না থাকলে `db.sqlite3`। কোনো Python ফাইল বদলাতে হয় না:
```
DATABASE_URL=postgres://user:pass@localhost:5432/ordermama
```
SQLite থেকে ডেটা নিতে: `python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission > data.json`, তারপর PostgreSQL সেট করে `migrate` ও `loaddata data.json`।

## সিকিউরিটি ও টেন্যান্ট আইসোলেশন
- প্রতিটি মডেলে `restaurant` ফরেন কি; স্টাফ API সব কোয়েরি নিজের রেস্টুরেন্টে সীমিত।
- অন্য রেস্টুরেন্টের অবজেক্ট ID অনুমান করে (মেনু, অর্ডার, টেবিল, স্টাফ) ছুঁলে **HTTP 403**।
- টেবিলের লিংকে অনুমান-অযোগ্য UUID; অর্ডারের জন্য স্বাক্ষরিত, মেয়াদী টেবিল-সেশন টোকেন; টোকেন ও IP ভিত্তিক রেট-লিমিট।
- দাম সবসময় সার্ভার ডেটাবেজ থেকে নেয় (ক্লায়েন্টের দাম অগ্রাহ্য)। আপলোড করা ছবি যাচাই করে WEBP-তে কম্প্রেস হয়।
- `DEBUG=False`-এ secure cookie, nosniff; HTTPS ও HSTS চালু করতে `.env`-এ `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`।
- প্রোডাকশনে `mock` পেমেন্ট গেটওয়ে বন্ধ।

- ডার্ক/লাইট মোড: ড্যাশবোর্ড ও সুপার-অ্যাডমিনের নিচে “থিম টগল” বাটন। পছন্দ localStorage-এ সেভ থাকে।

## নতুন ফিচার (সর্বশেষ)
- **কাস্টমার:** খাবারে “জনপ্রিয়” / “নতুন” ব্যাজ, পুরনো অর্ডার এক ক্লিকে আবার কার্টে (Re-order), ফোনে “অ্যাপ ইনস্টল” (PWA)।
- **মার্চেন্ট:** মেনু CSV ইমপোর্ট, প্রথম লগইনে অনবোর্ডিং চেকলিস্ট, টেবিল বোর্ড (খালি/চলমান/বিল বাকি), সেলস CSV এক্সপোর্ট, KOT প্রিন্ট (কিচেন টিকেট)।
- **সুপার অ্যাডমিন:** প্ল্যান ফিচার অন/অফ, মাসিক আয় গ্রাফ, পেন্ডিং পেমেন্ট অ্যালার্ট।

- বেসিক: শুধু মেনু। প্রিমিয়াম: লাইভ অর্ডার/KOT + QR PDF + ব্র্যান্ডিং (সুপার অ্যাডমিন থেকে ফিচার-ফ্ল্যাগ বদলানো যায়)।
- মেয়াদ শেষের ৩ দিন আগে মার্চেন্ট ড্যাশবোর্ডে সতর্কতা। মেয়াদ শেষে গ্রেস পিরিয়ড (প্রতি সাবস্ক্রিপশনে নির্ধারিত), তারপর কাস্টমার মেনু বন্ধ। পেমেন্ট হলেই অটো চালু।
- স্ট্যাটাস সবসময় তারিখ থেকে হিসাব হয়, তাই ব্যাকগ্রাউন্ড জব না চললেও লক ঠিক সময়ে কাজ করে। রিমাইন্ডার/রিপোর্টের জন্য দৈনিক একবার: `python manage.py check_subscriptions` (cron)।

## পেমেন্ট
`PAYMENT_GATEWAY=mock` (ডেভ) অথবা `sslcommerz` (স্টোর আইডি/পাসওয়ার্ড `.env`-এ)। বিকাশ/নগদ/রকেট SSLCommerz-এর মাধ্যমে। **লাইভ ক্রেডেনশিয়াল দিয়ে সত্যিকারের পেমেন্ট এখনো পরীক্ষা করা হয়নি** — আগে স্যান্ডবক্সে যাচাই করুন।

## ডিপ্লয়মেন্ট — জরুরি তথ্য
- **WebSocket (লাইভ অর্ডার) চালাতে ASGI সার্ভার (daphne) ও Redis লাগে।** সাধারণ cPanel শেয়ার্ড হোস্টিং-এর "Python App" WSGI চালায়, তাই সেখানে মেনু/ড্যাশবোর্ড চললেও লাইভ আপডেট চলবে না (ড্যাশবোর্ড প্রতি ২ সেকেন্ডে হালকা পালস-পোলিংয়ে ফিরে যায়)। লাইভ অর্ডারের জন্য VPS বা Docker ব্যবহার করুন।
- **`NUM_PROXIES`:** সামনে nginx/Apache থাকলে `NUM_PROXIES=1` দিন (প্রোডাকশনের ডিফল্টও ১), নইলে ক্লায়েন্ট `X-Forwarded-For` বানিয়ে IP রেট-লিমিট এড়াতে পারে। প্রক্সি ছাড়া সরাসরি খুললে `0`।
- **Redis:** প্রোডাকশনে `REDIS_URL` দেওয়া থাকলে কিন্তু Redis না চললে অ্যাপ চালুই হবে না (চুপচাপ মেমরিতে নামলে একাধিক ওয়ার্কারে লাইভ আপডেট ও রেট-লিমিট ভেঙে যায়)। একক-প্রসেসে ইচ্ছা করে নামাতে চাইলে `ALLOW_REDIS_FALLBACK=True`।
- ইমেজ/মিডিয়া (`media/`) nginx বা অবজেক্ট স্টোরেজ দিয়ে সার্ভ করুন (Django প্রোডাকশনে মিডিয়া সার্ভ করে না)।
- কনটেইনার: `cp .env.example .env && docker compose up --build` (Dockerfile/compose এখনো চালিয়ে পরীক্ষা করা হয়নি)।
- QR PDF-এ বাংলা লেখার জন্য সার্ভারে বাংলা-সমর্থিত ফন্ট লাগে (Docker ইমেজে FreeSans আছে; নিজের ফন্ট দিতে `QR_FONT_PATH`)।
- ফন্ট/আইকন Google Fonts ও unpkg CDN থেকে আসে; ইন্টারনেট ছাড়া ব্যবহার করলে নিজের সার্ভারে হোস্ট করুন।

## cPanel (Passenger) ডিপ্লয়
শেয়ার্ড হোস্টিং-এ মেনু, অর্ডার, ড্যাশবোর্ড সব চলে; লাইভ আপডেট ২ সেকেন্ডের হালকা পালস-পোলিংয়ে হয় (WebSocket নয়)।
1. cPanel → Setup Python App (Python 3.11, অ্যাপ রুট = রিপোর ফোল্ডার, `passenger_wsgi.py`); Git Version Control থেকে রিপো ক্লোন।
2. সার্ভারে `.env` বানান: `DJANGO_DEBUG=False`, লম্বা `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS=yourdomain.com`, `CSRF_TRUSTED_ORIGINS=https://yourdomain.com`, `SITE_BASE_URL=https://yourdomain.com`, `SERVE_MEDIA=True`।
3. **পুরনো db.sqlite3 থাকলে সরিয়ে ফেলুন** (অন্য প্রজেক্টের টেবিল থাকলে মাইগ্রেশন মিলবে না): `mv db.sqlite3 db_old.sqlite3`।
4. `.cpanel.yml` ডেপ্লয়ে নিজে `pip install`, `migrate`, `collectstatic` চালিয়ে অ্যাপ রিস্টার্ট করে। প্রথমবার ম্যানুয়ালি: `python manage.py createsuperuser`।

## টেস্ট
```bash
python manage.py test apps    # ৩২টি টেস্ট: অর্ডার ফ্লো, রোল, টেন্যান্ট আইসোলেশন, সাবস্ক্রিপশন, পেমেন্ট, WebSocket
```

## ফোল্ডার
`apps/` accounts · restaurants · menu · orders · subscriptions · payments · realtime · analytics · web (পেজ ও API) — `templates/{customer,dashboard,superadmin}`, `static/{css,js}`।
