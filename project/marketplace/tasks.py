from celery import shared_task
from marketplace.models import Discount, Food
from django.utils import timezone as tz
from vendor.utils import revert_discount
from django.db.transaction import atomic

@shared_task
def say_hello():
    print("Hello from Celery")
    return "Hello!"


@shared_task
def deactivate_discounts():
    discounts = Discount.objects.filter(deadline__lte=tz.now()).prefetch_related("foods")
    # resetting foods prices to original
    with atomic():    
        for dis in discounts:
            discount_foods = dis.foods.only("id","min_price","prices")
            for food in discount_foods:
                print("discount cleared by celery...",food.id)
                food = revert_discount(food, dis.amount)
            Food.objects.bulk_update(discount_foods, ["prices", "min_price"])
        discounts.update(
            is_active=False
        )
    return "Discounts Deactivated!"

