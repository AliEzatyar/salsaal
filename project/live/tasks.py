from celery import shared_task
from django.utils import timezone as tz

from live.models import Notification


@shared_task
def delete_notifications():
    print("deleting notifications.......")
    days_ago = tz.timedelta(days=15)
    now = tz.now()
    Notification.objects.filter(is_read=True,date_time__lt=now - days_ago).delete()
    return "Deleted!"
