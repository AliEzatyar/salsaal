import json
from celery import shared_task
from django.utils import timezone
from marketplace.utils import r
from marketplace.models import Food
from project.live.models import Notification
from project.live.utils import send_notification
from .models import (
    PLATFORM_DEFAULT_EVENING_QORAA_TITLE,
    PLATFORM_DEFAULT_MORNING_QORAA_TITLE,
    Qoraa,
    QoraaVendor,
)
from random import choice
from django.utils.translation import gettext as _
from django.utils.translation import deactivate as deactivate_language
from django.utils.translation import activate as activate_language


def _send_qoraa_creation_notification(vendor, qoraa, end_time):
    """Sends notification to vendor about qoraa creation."""
    activate_language("fa")
    title = _("Qoraa Sponsorship")
    description = _("You are a sponsor of this Qoraa at {time}.").format(time=end_time)
    notf = Notification.objects.create(
        receiver=vendor.user,
        title=title,
        description=description,
        type="QORAA_CREATED",
        data={},
        target_id=qoraa.id,
    )
    r.publish(
        f"pub:vendor:{vendor.id}",
        json.dumps(
            {
                "type": "NOTIFICATION",
                "data": {},
            }
        ),
    )
    send_notification.delay(
        vendor.user.id,
        notf.title,
        body=notf.description,
    )
    deactivate_language()


def _create_qoraas_for_time(hour, platform_qoraa_title):
    """
    Generic function to create qoraas for a specific time.

    Args:
        hour (int): The hour of the day to start the qoraa.
        platform_qoraa_title (str): The title for the platform-wide qoraa.
    """
    now = timezone.localtime()
    start = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    end = start + timezone.timedelta(hours=1)

    # ----------- platform's default qoraa --------------
    if not Qoraa.objects.filter(start=start, is_platform=True).exists():
        platform_qvs = QoraaVendor.objects.filter(is_platform=True).select_related('vendor__user')
        if platform_qvs.exists():
            random_qv = choice(list(platform_qvs))
            if random_qv.food_items:
                random_food_id = choice(random_qv.food_items)
                food = Food.objects.filter(pk=random_food_id).first()
                if food:
                    activate_language("fa")
                    q = Qoraa.objects.create(
                        vendor=random_qv.vendor,
                        food=food,
                        start=start,
                        end=end,
                        status=Qoraa.STATUS_RUNNING,
                        title=_(platform_qoraa_title),
                        is_platform=True,
                    )
                    deactivate_language()
                    _send_qoraa_creation_notification(random_qv.vendor, q, end)

    # ------------ creating vendors custom qoraas --------------
    qvs = QoraaVendor.objects.filter(
        is_active=True, start_date__lte=now.date(), end_date__gte=now.date()
    ).select_related('vendor__user')
    
    all_food_ids = []
    for qv in qvs:
        if qv.food_items:
            all_food_ids.extend(qv.food_items)
    
    foods = Food.objects.in_bulk(list(set(all_food_ids)))

    for qv in qvs:
        if not qv.food_items:
            continue
        
        random_food_id = choice(qv.food_items)
        food = foods.get(random_food_id)

        if not food:
            continue
            
        q, created = Qoraa.objects.get_or_create(
            vendor=qv.vendor,
            start=start,
            defaults={
                "end": end,
                "status": Qoraa.STATUS_RUNNING,
                "title": qv.title,
                "food": food,
            },
        )

        if created:
            _send_qoraa_creation_notification(qv.vendor, q, end)


@shared_task
def create_morning_qoraa():
    """
    Creates the morning qoraa (lottery) which runs from 11:00 to 12:00 local time.
    """
    _create_qoraas_for_time(11, PLATFORM_DEFAULT_MORNING_QORAA_TITLE)
    return "Morning Qoraas Created"


@shared_task
def create_evening_qoraa():
    """
    Creates the evening qoraa (lottery) which runs from 18:00 to 19:00 local time.
    """
    _create_qoraas_for_time(18, PLATFORM_DEFAULT_EVENING_QORAA_TITLE)
    return "Evening Qoraas Created"


def finalize_qoraa():
    """
    Finalizes any qoraa that is currently in the 'RUNNING' state but whose
    'end' time has passed.

    This function iterates through all such qoraas, randomly selects a winner
    from the list of joiners, updates the qoraa's status to 'FINISHED', and
    assigns the winner.

    If a qoraa has no joiners, it is simply marked as 'FINISHED' without a winner.

    Returns:
        list: A list of dictionaries, where each dictionary contains the primary
              key of the finalized qoraa and its winner's primary key (or None).
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
        # ---------------- sending notification to winner --------------
        if winner:
            activate_language("fa")
            title = _("Qoraa Winner")
            description = _(
                "Congratulations! You have won the Qoraa sponsored by {vendor}"
            ).format(vendor=q.vendor.vendor_name)
            notf = Notification.objects.create(
                receiver=winner,
                title=title,
                description=description,
                type="QORAA_WINNER",
                data={},
                target_id=q.id,
            )
            r.publish(
                f"pub:user:{winner.id}",
                json.dumps(
                    {
                        "type": "NOTIFICATION",
                        "data": {},
                    }
                ),
            )
            send_notification.delay(
                winner.id,
                notf.title,
                body=notf.description,
            )
            deactivate_language()
        results.append({"qoraa": q.pk, "winner": getattr(winner, "pk", None)})
    return results


@shared_task
def finalize_morning_qoraa():
    """
    Celery task wrapper to finalize morning qoraas.
    This task simply calls the main `finalize_qoraa` logic.
    """
    return finalize_qoraa()


@shared_task
def finalize_evening_qoraa():
    """
    Celery task wrapper to finalize evening qoraas.
    This task simply calls the main `finalize_qoraa` logic.
    """
    return finalize_qoraa()
