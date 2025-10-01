from django.conf import settings as s
from redis import Redis
from marketplace.utils import r


def to_af_weekday(index):
    return (9 + index) % 7 + 1


def get_vendor_carriers_key(id):
    return f"vendor:{id}:carriers"


def revert_discount(food, discount_amount):
    prices = []
    for price in food.prices:
        prices.append(price * 100 // (100 - discount_amount))
    food.prices = prices
    food.min_price = min(prices)
    return food


def apply_discount(food,discount_amount):
    prices = []
    for price in food.prices:
        prices.append(price * (100 - discount_amount) // 100)
    food.prices = prices
    food.min_price = min(prices)
    return food

