"""টেবিল-সেশন টোকেন: স্বাক্ষরিত, মেয়াদী; কাস্টমারকে নির্দিষ্ট টেবিলের সাথে বেঁধে রাখে।"""
from django.conf import settings
from django.core import signing

SALT = "ordermama.table-session"


def make_table_token(table):
    return signing.dumps({"r": table.restaurant_id, "t": table.pk}, salt=SALT)


def read_table_token(token):
    """সঠিক হলে {"r":..,"t":..} ফেরত দেয়, নইলে None।"""
    try:
        return signing.loads(token, salt=SALT, max_age=settings.TABLE_SESSION_MAX_AGE)
    except signing.BadSignature:
        return None
