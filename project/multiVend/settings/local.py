from multiVend.settings.base import *
from os import environ as env

ALLOWED_HOSTS = ["*"]
LOCAL = True
DATABASES = {
    "default": {
        # "ENGINE": "django.db.backends.postgresql",
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "PORT": config("DB_PORT", cast=int),
        "HOST": config("DB_HOST"),
        "CONN_MAX_AGE": config("CONN_MAX_AGE", cast=int),  # pgbouncer
    }
}

SECRET_KEY = config("SECRET_KEY", cast=str)
DUMMY_SECRET = config("DUMMY_SECRET", cast=str)
# Redis as its own
REDIS_HOST = config("REDIS_HOST")
REDIS_PORT = config("REDIS_PORT", cast=int)
REDIS_DB = config("REDIS_DB")
REDIS_PASSWORD = config("REDIS_PASSWORD")

# CACHING
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",  #
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
# django channels
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
            "password": REDIS_PASSWORD,
        },
    },
}


CURRENT_DOMAIN_NAME = config("CURRENT_DOMAIN_NAME", cast=str)
# for react, cross site
CORS_ALLOWED_ORIGINS = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_ALL_ORIGINS = True
# Celery settings
# Celery settings
CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"  # or use RabbitMQ
CELERY_RESULT_BACKEND = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
DJANGO_CELERY_BEAT_MAX_LOOP_INTERVAL = 10 # every 10 seconds, jobs re-taken from db
# Celery Beat for periodic tasks
INSTALLED_APPS += ["django_celery_beat", "storages"]


# S3 config

AWS_STORAGE_BUCKET_NAME = "food-delivery-images-prod"
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
AWS_QUERYSTRING_AUTH = True  # so URLs are clean, no ?X-Amz-Signature=...
AWS_S3_REGION_NAME = env.get(
    "AWS_S3_REGION_NAME"
)  # change if your bucket is in another region # change if your bucket is in another region
AWS_S3_SIGNATURE_VERSION = "s3v4"
# Tell Django to use S3 for media storage
# Public URL of your bucket (can be S3 or CloudFront CDN)
MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/"

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": open(BASE_DIR.parent / "private.pem").read(),
    "VERIFYING_KEY": open(BASE_DIR.parent / "public.pem").read(),
    "ACCESS_TOKEN_LIFETIME": timedelta(days=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=120),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}


# Firebase cloud messageing
import firebase_admin
from firebase_admin import credentials, messaging

# Replace 'path/to/your/serviceAccountKey.json' with the actual path
# It's better to load this path from Django settings or environment variables for production
cred = credentials.Certificate(config("FIREBASE_SERVICE_ACCOUNT_KEY"))
firebase_admin.initialize_app(cred)
FCM_API_KEY = config("FIREBASE_SERVICE_ACCOUNT_KEY")


# zego cloud
ZEGOCLOUD_APP_ID = config("ZEGOCLOUD_APP_ID")
ZEGOCLOUD_SERVER_SECRET = config("ZEGOCLOUD_SERVER_SECRET")


# hesab pay
HESAB_PAY_ENDPOINT = config("HESAB_PAY_ENDPOINT")
HESAB_PAY_API_KEY = config("HESAB_PAY_API_KEY")
HESAB_PAY_MULTI_VENDOR_ENDPOINT = config("HESAB_PAY_MULTI_VENDOR_ENDPOINT")
