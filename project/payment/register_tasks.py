from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json


def register_periodic_tasks():
    """
    """
    timezone = "Asia/Kabul"
    # create morning at 6:00
    create_morning_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=0,
        hour=10,
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=timezone,
    )
    task, created = PeriodicTask.objects.get_or_create(
        name="GET exchage rate",
        task="payment.tasks.update_afn_usd_rate",
        defaults={"crontab": create_morning_schedule, "args": json.dumps([])},
    )
    if not created:
        task.crontab = create_morning_schedule
        task.enabled = True
        task.save()
