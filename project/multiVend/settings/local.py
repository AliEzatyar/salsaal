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
        "CONN_MAX_AGE": config("CONN_MAX_AGE",cast=int), # pgbouncer
    }
}

SECRET_KEY = config("SECRET_KEY",cast=str)
