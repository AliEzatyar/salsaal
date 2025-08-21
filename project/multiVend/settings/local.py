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

# Redis as its own
REDIS_HOST = config("REDIS_HOST")
REDIS_PORT = config("REDIS_PORT", cast=int)
REDIS_DB = config("REDIS_DB")
# CACHING
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",  #
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
CELERY_BROKER_URL = "redis://localhost:6379/0"  # or use RabbitMQ
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

# Celery Beat for periodic tasks
INSTALLED_APPS += ["django_celery_beat", "storages"]


# S3 config

AWS_STORAGE_BUCKET_NAME = "food-delivery-images-prod"
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
AWS_QUERYSTRING_AUTH = True  # so URLs are clean, no ?X-Amz-Signature=...
AWS_S3_REGION_NAME = "us-east-1"  # change if your bucket is in another region
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


