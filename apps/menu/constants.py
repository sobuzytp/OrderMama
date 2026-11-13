"""মেনু সংক্রান্ত শেয়ার্ড ধ্রুবক।"""

# কাস্টমার মেনুতে “নতুন” ব্যাজ কত দিন থাকবে
NEW_BADGE_DAYS = 14

# CSV ইমপোর্টে সর্বোচ্চ কত লাইন নেওয়া হবে (বড় ফাইলে সার্ভার যেন আটকে না যায়)
CSV_MAX_ROWS = 500
CSV_MAX_BYTES = 512 * 1024

# ফিচার flags যেগুলো প্ল্যানে on/off করা যায়
PLAN_FEATURES = ("live_orders", "qr_generator", "branding")
