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
INSTALLED_APPS += ["django_celery_beat"]
