from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json

from project.qoraa.models import PLATFORM_EVENING_QORAA_END_HOUR, PLATFORM_EVENING_QORAA_START_HOUR, PLATFORM_MORNING_QORAA_END_HOUR, PLATFORM_MORNING_QORAA_START_HOUR


def register_periodic_tasks():
    """
    Register daily crontab tasks to create and finalize Qoraa lotteries.

    Four tasks are created:
      - create morning lottery at 11:00
      - finalize morning lottery at 12:00
      - create evening lottery at 18:00
      - finalize evening lottery at 19:00

    Uses timezone 'Asia/Kabul' to match other registered tasks in the project.
    """
    timezone = "Asia/Kabul"
    # create morning at 8:00
    create_morning_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour=str(PLATFORM_MORNING_QORAA_START_HOUR),
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=timezone,
    )
    task, created = PeriodicTask.objects.get_or_create(
        name="Create Platform Morning Qoraa",
        task="qoraa.tasks.create_morning_qoraa",
        defaults={"crontab": create_morning_schedule, "args": json.dumps([])},
    )
    if not created:
        task.crontab = create_morning_schedule
        task.enabled = True
        task.save()
    # finalize morning at 12:00
    finalize_morning_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour=str(PLATFORM_MORNING_QORAA_END_HOUR), day_of_week="*", day_of_month="*", month_of_year="*", timezone=timezone
    )
    task, created = PeriodicTask.objects.get_or_create(
        name="Finalize Morning Qoraa",
        task="qoraa.tasks.finalize_morning_qoraa",
        defaults={"crontab": finalize_morning_schedule, "args": json.dumps([])},
    )
    if not created:
        task.crontab = finalize_morning_schedule
        task.enabled = True
        task.save()
    # create evening at 15:00
    create_evening_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0", hour=str(PLATFORM_EVENING_QORAA_START_HOUR), day_of_week="*", day_of_month="*", month_of_year="*", timezone=timezone
    )
    task, created = PeriodicTask.objects.get_or_create(
        name="Create Platform Evening Qoraa",
        task="qoraa.tasks.create_evening_qoraa",
        defaults={"crontab": create_evening_schedule, "args": json.dumps([])},
    )
    if not created:
        task.crontab = create_evening_schedule
        task.enabled = True
        task.save()

    # finalize evening at 18:00
    finalize_evening_schedule, _ = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour=str(PLATFORM_EVENING_QORAA_END_HOUR),
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=timezone,
    )
    task, created = PeriodicTask.objects.get_or_create(
        name="Finalize Evening Qoraa",
        task="qoraa.tasks.finalize_evening_qoraa",
        defaults={"crontab": finalize_evening_schedule, "args": json.dumps([])},
    )
    if not created:
        task.crontab = finalize_evening_schedule
        task.enabled = True
        task.save()
    return True
