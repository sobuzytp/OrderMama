import os
import sys

# আপনার প্রজেক্টের পাথ সেট করা হচ্ছে
sys.path.insert(0, '/home/lxhytteluf/ordermama.notte.top')

# আপনার জ্যাঙ্গো প্রজেক্টের মেইন কনফিগারেশন ফোল্ডারের নাম (config) এখানে দিন
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
