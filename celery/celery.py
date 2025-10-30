from celery import Celery
from os import environ

environ.setdefault("DJANGO_SETTINGS_MODULE", "project.multiVend.settings.prod")

app = Celery("multiVend")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
