from celery import shared_task
from marketplace.models import Discount
from django.utils import timezone as tz


@shared_task
def say_hello():
    print("Hello from Celery")
    return "Hello!"


@shared_task
def deactivate_discounts():
    print("deactivating discounts")
    Discount.objects.filter(deadline__lte=tz.now()).update(
        is_active=False
    )

    return "Deactivated!"
