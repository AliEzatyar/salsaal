from multiVend.settings.base import *
from os import environ as env

ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env.get("DB_NAME"),
        "USER": env.get("DB_USER"),
        "PASSWORD": env.get("DB_PASSWORD"),
        "PORT": env.get("DB_PORT"),
        "HOST": env.get("DB_HOST"),
    }
}

SECRET_KEY = env.get("SECRET_KEY")
LOCAL = False