import json
from celery import shared_task
from django.utils import timezone
from marketplace.utils import r
from marketplace.models import Food
from live.models import Notification
from live.utils import send_notification
from .models import (
    PLATFORM_DEFAULT_EVENING_QORAA_TITLE,
    PLATFORM_DEFAULT_MORNING_QORAA_TITLE,
    Qoraa,
    PlatformQoraaVendor,
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
        platform_qoraa_vendors = PlatformQoraaVendor.objects.filter(is_active=True)
        random_qv = choice(platform_qoraa_vendors) if platform_qoraa_vendors else None
        if random_qv and random_qv.food_items:  
            random_food_id = choice(random_qv.food_items.all().values_list("id", flat=True))
            food = Food.objects.filter(pk=random_food_id).first()
            if food:
                activate_language(random_qv.vendor.user.profile.pf_lang)
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
            activate_language(winner.profile.pf_lang)
            title = _("Qoraa Winner")
            sponser = _("Zaytoon Food") if q.is_platform else q.vendor.vendor_name
            description = _(
                "Congratulations! You have won the Qoraa sponsored by {sponser}"
            ).format(sponser=sponser)
            notf = Notification.objects.create(
                receiver=winner,
                title=title,
                description=description,
                type="QORAA_WINNER",
                data={},
                target_id=q.id,
            )
            send_notification.delay(
                winner.id,
                notf.title,
                body=notf.description,
                data={"qoraa_id": q.id},
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


@shared_task
def start_vendor_qoraa(qoraa_id):
    """
    Celery task to start a vendor's qoraa by setting its status to 'RUNNING'.
    
    Args:
        qoraa_id (int): The primary key of the Qoraa to be started.
    
    Returns:
        str: A message indicating the result of the operation.
    """
    try:
        qoraa = Qoraa.objects.get(pk=qoraa_id)
        qoraa.status = Qoraa.STATUS_RUNNING
        qoraa.save(update_fields=["status"])
        return f"Qoraa {qoraa_id} started."
    except Qoraa.DoesNotExist:
        return f"Qoraa {qoraa_id} does not exist."

@shared_task
def end_vendor_qoraa(qoraa_id):
    """
    Celery task to end a vendor's qoraa by finalizing it.
    
    Args:
        qoraa_id (int): The primary key of the Qoraa to be ended.
    
    Returns:
        str: A message indicating the result of the operation.
    """
    try:
        qoraa = Qoraa.objects.get(pk=qoraa_id)
        if qoraa.status == Qoraa.STATUS_RUNNING:
            joiners = list(qoraa.joiners.all())
            winner = None
            if joiners:
                winner = choice(joiners)
                qoraa.winner = winner
            qoraa.status = Qoraa.STATUS_FINISHED
            qoraa.save()
            # Notify the winner if there is one
            if winner:
                activate_language(winner.profile.pf_lang)
                title = _("Qoraa Winner")
                description = _(
                    "Congratulations! You have won the Qoraa sponsored by {sponser}"
                ).format(sponser= qoraa.vendor.vendor_name)
                notf = Notification.objects.create(
                    receiver=winner,
                    title=title,
                    description=description,
                    type="QORAA_WINNER",
                    data={},
                    target_id=qoraa.id,
                )

                send_notification.delay(
                    winner.id,
                    notf.title,
                    body=notf.description,
                    data={"qoraa_id": qoraa.id},
                )
                deactivate_language()
            return f"Qoraa {qoraa_id} ended."
        else:
            return f"Qoraa {qoraa_id} is not running."
    except Qoraa.DoesNotExist:
        return f"Qoraa {qoraa_id} does not exist."
