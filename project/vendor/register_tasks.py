import logging
import json

from django.conf import settings
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule

from live.models import OLD_NOTIFICAITON_EXPIRE_DAYS

logger = logging.getLogger(__name__)


def _ensure_crontab_task(name, task_path, minute, hour, timezone_str="Asia/Kabul", args=None):
    """
    Ensure a crontab + PeriodicTask exists and is enabled.
    Returns the PeriodicTask instance.
    """
    schedule, _ = CrontabSchedule.objects.get_or_create(
        minute=minute,
        hour=hour,
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
        timezone=timezone_str,
    )

    defaults = {"crontab": schedule, "args": json.dumps(args or [])}
    task, created = PeriodicTask.objects.get_or_create(name=name, task=task_path, defaults=defaults)
    if not created:
        # keep schedule and enabled state up-to-date
        task.crontab = schedule
        task.args = json.dumps(args or [])
        task.enabled = True
        task.save()
        logger.debug("Updated existing periodic task: %s", name)
    else:
        logger.info("Created periodic task: %s", name)
    return task


def _ensure_interval_task(name, task_path, every, period, args=None):
    """Ensure an interval schedule + PeriodicTask exists and is enabled."""
    schedule, _ = IntervalSchedule.objects.get_or_create(every=every, period=period)
    defaults = {"interval": schedule, "args": json.dumps(args or [])}
    task, created = PeriodicTask.objects.get_or_create(name=name, task=task_path, defaults=defaults)
    if not created:
        task.interval = schedule
        task.args = json.dumps(args or [])
        task.enabled = True
        task.save()
        logger.debug("Updated existing interval task: %s", name)
    else:
        logger.info("Created interval task: %s", name)
    return task


def register_periodic_tasks():
    """
    Register periodic tasks for vendor-related background work.

    This function is idempotent and safe to call multiple times (it uses get_or_create
    and updates existing PeriodicTask entries).
    """
    tz = getattr(settings, "DEFAULT_TIMEZONE", "Asia/Kabul")

    try:
        # Reset vendors carriers status at 01:00 AM daily
        _ensure_crontab_task(
            name="Reset Vendors Carriers Status",
            task_path="vendor.tasks.reset_vendors_carriers_in_redis",
            minute="0",
            hour="1",
            timezone_str=tz,
        )

        # Deactivate expired discounts every hour
        _ensure_interval_task(
            name="Deactivate Dead Discounts every 1 hour",
            task_path="vendor.tasks.deactivate_discounts",
            every=1,
            period=IntervalSchedule.HOURS,
        )

        # Disable vendors every  hour
        _ensure_interval_task(
            name="Disable Vendors Every 5 hours",
            task_path="vendor.tasks.disable_vendors",
            every=5,
            period=IntervalSchedule.HOURS,
        )

        # Delete old notifications on a schedule defined by OLD_NOTIFICAITON_EXPIRE_DAYS
        _ensure_interval_task(
            name="Delete Old Notifications",
            task_path="live.tasks.delete_notifications",
            every=OLD_NOTIFICAITON_EXPIRE_DAYS,
            period=IntervalSchedule.DAYS,
        )

    except Exception:
        # We intentionally catch broad exceptions here because this runs at app startup
        # (post_migrate) and must not break the application if celery-beat isn't ready.
        logger.exception("Failed to register periodic tasks for vendor app")

    return True
