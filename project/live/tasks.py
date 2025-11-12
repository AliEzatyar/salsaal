from celery import shared_task
from django.utils import timezone as tz
from .models import OLD_NOTIFICAITON_EXPIRE_DAYS
from live.models import Notification


@shared_task
def delete_notifications():
    days_ago = tz.timedelta(days=OLD_NOTIFICAITON_EXPIRE_DAYS)
    now = tz.now()
    Notification.objects.filter(is_read=True,date_time__lt=now - days_ago).delete()
    return "Deleted!"


