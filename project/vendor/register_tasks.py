from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
import json

from live.models import OLD_NOTIFICAITON_EXPIRE_DAYS


def register_periodic_tasks():
    # ----------------------- vendor carriers status revert- crontab---------------------------------
    # creating the crontab schedule
    revert_carriers_schedule, created = CrontabSchedule.objects.get_or_create(
        minute="0",
        hour="1",
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone="Asia/Kabul",  # important
    )

    # creating the periodic task
    task, created = PeriodicTask.objects.get_or_create(
        name="Reset Vendors Carriers Status",  # Unique name
        task="vendor.tasks.reset_vendors_carriers_in_redis",  # path to task
        defaults={
            "crontab": revert_carriers_schedule,
            "args": json.dumps([]),  # optional
        },
    )

    if not created:
        # Update if already exists
        print("already existed")
        task.crontab = revert_carriers_schedule
        task.enabled = True
        task.save()
    # ------------------------- discount revert task- interval  --------------------------------------
    deactivate_discount_schedule, created = IntervalSchedule.objects.get_or_create(
        every=1, period=IntervalSchedule.HOURS
    )

    deactivate_discount_task, created = PeriodicTask.objects.get_or_create(
        name="Deactivate Dead Discounts",  # Unique name
        task="vendor.tasks.deactivate_discounts",  # path to task
        defaults={
            "interval": deactivate_discount_schedule,
            "args": json.dumps([]),  # optional
        },
    )

    if not created:
        print("already exists")
        deactivate_discount_task.interval = deactivate_discount_schedule
        deactivate_discount_task.save()
    # ------------------------------ delete notifications  --------------------------------------
    delete_notifications_schedule, created = IntervalSchedule.objects.get_or_create(
        every=OLD_NOTIFICAITON_EXPIRE_DAYS, period=IntervalSchedule.DAYS
    )

    delete_notifications_task, created = PeriodicTask.objects.get_or_create(
        name="Delete Old Notifications",  # Unique name
        task="live.tasks.delete_notifications",  # path to task
        defaults={
            "interval": delete_notifications_schedule,
            "args": json.dumps([]),  # optional
        },
    )

    if not created:
        print("already exists")
        delete_notifications_task.interval = delete_notifications_schedule
        delete_notifications_task.save()
