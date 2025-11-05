from celery import shared_task
from django.utils import timezone
from .models import PLATFORM_DEFAULT_EVENING_QORAA_TITLE, PLATFORM_DEFAULT_MORNING_QORAA_TITLE, Qoraa, QoraaVendor
from random import choice
from django.utils.translation import gettext as _
from django.utils.translation import deactivate as deactivate_language
from django.utils.translation import activate as activate_language


@shared_task
def create_morning_qoraa():
    """Create the morning lottery (11:00 - 12:00).
    NOTE: we assume server stores timezone-aware datetimes. This task will create
    a Qoraa instance for today's date between 11:00 and 12:00 local time.
    """
    # ----------- platform's default qoraa --------------
    now = timezone.localtime()
    start = now.replace(hour=11, minute=0, second=0, microsecond=0)
    end = start + timezone.timedelta(hours=1)
    # If start is in the past (e.g. task executed slightly after 11:00), still create if not exists
    exists = Qoraa.objects.filter(start=start).exists()
    if not exists:
        # Create the Qoraa instance, vendors also be choosen randomly during finalization
        activate_language("fa")
        q = Qoraa.objects.create(
            start=start,
            end=end,
            status=Qoraa.STATUS_RUNNING,
            title=_(PLATFORM_DEFAULT_MORNING_QORAA_TITLE),
        )
        deactivate_language()
    # ------------ creating vendors custom qoraas --------------
    qvs = QoraaVendor.objects.filter(is_active=True, start_date__lte=now.date(), end_date__gte=now.date())
    for qv in qvs:
        q, created = Qoraa.objects.get_or_create(vendor=qv.vendor, start=start, defaults={"end": end, "status": Qoraa.STATUS_RUNNING, "title": qv.title})

    return "Morning Qoraas Created"


def finalize_qoraa():
    """Finalize the morning lottery (select winner, mark finished).
    This task finds yesterday/today lotteries that ended and are still running.
    """
    now = timezone.now()
    to_finalize = Qoraa.objects.filter(status=Qoraa.STATUS_RUNNING, end__lte=now)
    results = []
    for q in to_finalize:
        joiners = list(q.joiners.all())
        winner = None
        if joiners:
            winner = choice(joiners)
            q.winner = winner
        q.status = Qoraa.STATUS_FINISHED
        q.save()
        results.append({"qoraa": q.pk, "winner": getattr(winner, "pk", None)})
    return results


@shared_task
def finalize_morning_qoraa():
    """Finalize morning lotteries/qoraas."""
    return finalize_qoraa() 


@shared_task
def finalize_evening_qoraa():
    """Finalize evening lotteries/qoraas."""
    return finalize_qoraa()


def create_evening_qoraa():
    """Create the evening lottery (18:00 - 19:00).
    """
    now = timezone.localtime()
    start = now.replace(hour=18, minute=0, second=0, microsecond=0)
    end = start + timezone.timedelta(hours=1)
    exists = Qoraa.objects.filter(start=start).exists()
    if not exists:
        q = Qoraa.objects.create(
            start=start,
            end=end,
            status=Qoraa.STATUS_RUNNING,
            title=_(PLATFORM_DEFAULT_EVENING_QORAA_TITLE),
        )

    # ------------ creating vendors custom qoraas --------------
    qvs = QoraaVendor.objects.filter(
        is_active=True, start_date__lte=now.date(), end_date__gte=now.date()
    )
    for qv in qvs:
        q, created = Qoraa.objects.get_or_create(
            vendor=qv.vendor,
            start=start,
            defaults={"end": end, "status": Qoraa.STATUS_RUNNING, "title": qv.title},
        )
        
    return "Evening Qoraas Created"
