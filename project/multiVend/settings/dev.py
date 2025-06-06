from multiVend.settings.base import *
from os import environ as env

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        # "ENGINE": "django.db.backends.postgresql",
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env.get("DB_NAME"),
        "USER": env.get("DB_USER"),
        "PASSWORD": env.get("DB_PASSWORD"),
        "PORT": env.get("DB_PORT"),
        "HOST": env.get("DB_HOST"),
        "OPTIONS": {"sslcert": "/sxx/.postgresql/postgresql.crt"},
    }
}

SECRET_KEY = env.get("SECRET_KEY")
LOCAL = False

# Redis as its own
REDIS_HOST = env.get("REDIS_HOST")
REDIS_PORT = env.get("REDIS_PORT")
REDIS_DB = env.get("REDIS_DB")

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

# current domain name
CURRENT_DOMAIN_NAME = env.get("CURRENT_DOMAIN_NAME")

# ssl for uvicorn, for uwsgi, we used include uswgi_params
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
