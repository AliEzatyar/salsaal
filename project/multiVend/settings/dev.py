"""this setting file is for pre-CI/CD deployment settings"""

from multiVend.settings.base import *
from os import environ as env


ALLOWED_HOSTS = ["*"]

DATABASES = {
    "default": {
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
REDIS_PASSWORD = env.get("REDIS_PASSWORD")

# CACHING
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",  #
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            # also supply password explicitly; some environments/clients pick this up more reliably
            "PASSWORD": REDIS_PASSWORD,
        },
        "KEY_PREFIX": "dj",
    }
}
# django channels
# Use a redis URL that includes the password so channels_redis/aioredis sees auth
# (some versions ignore a separate "password" key when hosts are tuples)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # supply a full redis URL including password and DB
            "hosts": [
                f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
            ],
        },
    },
}

# current domain name
CURRENT_DOMAIN_NAME = env.get("CURRENT_DOMAIN_NAME")

# ssl for uvicorn, for uwsgi, we used include uswgi_params
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Celery settings
CELERY_BROKER_URL = env.get("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env.get("CELERY_RESULT_BACKEND")
DJANGO_CELERY_BEAT_MAX_LOOP_INTERVAL = 50  # every 50 seconds, jobs re-taken from db
# Use django-celery-beat DatabaseScheduler so periodic tasks stored in the DB are used.
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Celery Beat for periodic tasks
INSTALLED_APPS += ["django_celery_beat", "storages"]


# S3 config

AWS_STORAGE_BUCKET_NAME = env.get("AWS_STORAGE_BUCKET_NAME")
AWS_ACCESS_KEY_ID = env.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env.get("AWS_SECRET_ACCESS_KEY")
AWS_QUERYSTRING_AUTH = True  # images have ?X-Amz-Signature=...
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


FCM_API_KEY = env.get("FIREBASE_SERVICE_ACCOUNT_KEY")

# AES encryption in order delivery token
DUMMY_SECRET = env.get("DUMMY_SECRET")
SECRET_KEY = env.get("SECRET_KEY")
# zego cloud
ZEGOCLOUD_APP_ID = env.get("ZEGOCLOUD_APP_ID")
ZEGOCLOUD_SERVER_SECRET = env.get("ZEGOCLOUD_SERVER_SECRET")

# hesab pay
HESAB_PAY_ENDPOINT = env.get("HESAB_PAY_ENDPOINT")
HESAB_PAY_API_KEY = env.get("HESAB_PAY_API_KEY")
HESAB_PAY_MULTI_VENDOR_ENDPOINT = env.get("HESAB_PAY_MULTI_VENDOR_ENDPOINT")
HESAB_PAY_ACCOUNT_PIN = env.get("HESAB_PAY_ACCOUNT_PIN")
HESAB_PAY_TRANSACTION_DETAILS_ENDPOINT = env.get("HESAB_PAY_TRANSACTION_DETAILS_ENDPOINT")
# stripe
STRIPE_SECRET_KEY = env.get("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = env.get("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = env.get("STRIPE_WEBHOOK_SECRET")

# exchange api
EXCHANGERATEHOSTKEY = env.get("EXCHANGERATEHOSTKEY")
EXCHANGE_URL = env.get("EXCHANGE_URL")

# cpass
CPAAS_AUTHENTICATION_URL = env.get("CPAAS_AUTHENTICATION_URL")
CPAAS_CALLER_ID = env.get("CPAAS_CALLER_ID")
CPAAS_USERNAME = env.get("CPAAS_USERNAME")
CPAAS_PASSWORD = env.get("CPAAS_PASSWORD")
CPAAS_UPLOAD_BASELOAD_URL = env.get("CPAAS_UPLOAD_BASELOAD_URL")
CPAAS_OBD_CAMPAIGN_ID = env.get("CPAAS_OBD_CAMPAIGN_ID")

# WHATSAPP_SUPPORT_NUMBER
WHATSAPP_SUPPORT_NUMBER = env.get("WHATSAPP_SUPPORT_NUMBER")

# TELEGRAM BOT
TELEGRAM_API_URL = env.get("TELEGRAM_API_URL")
TELEGRAM_BOT_TOKEN = env.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_BOT_URL = f"{TELEGRAM_API_URL}{TELEGRAM_BOT_TOKEN}/sendMessage"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": (
                '{{"time": "{asctime}", '
                '"level": "{levelname}", '
                '"logger": "{name}", '
                '"lineno": "{lineno}", '
                '"message": "{message}"}}'
            ),
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "vendor": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "live": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "order": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "accounts": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "marketplace": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "carrier": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "cart": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "qoraa": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "payment": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
