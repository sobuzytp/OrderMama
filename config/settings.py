import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
BASE_DIR=Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR/".env")
SECRET_KEY=os.getenv("SECRET_KEY","unsafe-development-key-change-me")
DEBUG=os.getenv("DEBUG","0")=="1"
ALLOWED_HOSTS=os.getenv("ALLOWED_HOSTS","localhost,127.0.0.1").split(",")
INSTALLED_APPS=["django.contrib.admin","django.contrib.auth","django.contrib.contenttypes","django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles","rest_framework","channels","core"]
MIDDLEWARE=["django.middleware.security.SecurityMiddleware","django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware","django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware","django.contrib.messages.middleware.MessageMiddleware","django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF="config.urls"; WSGI_APPLICATION="config.wsgi.application"; ASGI_APPLICATION="config.asgi.application"
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE_DIR/"templates"],"APP_DIRS":True,"OPTIONS":{"context_processors":["django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
db=os.getenv("DATABASE_URL")
DATABASES={"default":dj_database_url.parse(db,conn_max_age=600) if db else {"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"db.sqlite3"}}
LANGUAGE_CODE="bn"; TIME_ZONE="Asia/Dhaka"; USE_I18N=True; USE_TZ=True
STATIC_URL="static/"; STATIC_ROOT=BASE_DIR/"staticfiles"; MEDIA_URL="media/"; MEDIA_ROOT=BASE_DIR/"media"
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
LOGIN_URL="/accounts/login/"
REDIS_URL=os.getenv("REDIS_URL","")
CHANNEL_LAYERS={"default":{"BACKEND":"channels_redis.core.RedisChannelLayer","CONFIG":{"hosts":[REDIS_URL]}}} if REDIS_URL else {"default":{"BACKEND":"channels.layers.InMemoryChannelLayer"}}
REST_FRAMEWORK={"DEFAULT_PERMISSION_CLASSES":["rest_framework.permissions.IsAuthenticatedOrReadOnly"]}
