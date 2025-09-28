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

# Celery settings
CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"  # or use RabbitMQ
CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# Celery Beat for periodic tasks
INSTALLED_APPS += ["django_celery_beat", "storages"]


# S3 config

AWS_STORAGE_BUCKET_NAME = env.get("AWS_STORAGE_BUCKET_NAME")
AWS_ACCESS_KEY_ID = env.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env.get("AWS_SECRET_ACCESS_KEY")
AWS_QUERYSTRING_AUTH = True  # images have ?X-Amz-Signature=...
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

SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": open(BASE_DIR.parent / "private.pem").read(),
    "VERIFYING_KEY": open(BASE_DIR.parent / "public.pem").read(),
    "ACCESS_TOKEN_LIFETIME": timedelta(days=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=120),
}


FCM_API_KEY = env.get("FIREBASE_SERVICE_ACCOUNT_KEY")

# AES encryption in order delivery
DUMMY_SECRET = env.get("DUMMY_SECRET")
