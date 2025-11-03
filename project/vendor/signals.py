from django.db.models.signals import pre_delete
from django.dispatch import receiver
from marketplace.models import Discount, Food
from vendor.utils import revert_discount
from django.db import transaction


@receiver(pre_delete, sender=Discount)
def revert_food_prices_after_discount_deletion(sender, instance, **kwargs):

    discount = instance
    foods = discount.foods.only("id", "min_price", "prices")
    with transaction.atomic():
        for food in foods:
            revert_discount(food, discount.amount)
        Food.objects.bulk_update(foods, ["prices", "min_price"])

