from json import dumps
from marketplace.utils import r


def to_af_weekday(index):

    return (9 + index) % 7 + 1


def get_vendor_carriers_key(id):
    """
    this key enables access to f_c_c, b_c_c and total_c_c of a vendor
    mainly used in CalculateOrderTimeAndDeliveryCost
    """
    return f"vendor:{id}:carriers"


def revert_discount(food, discount_amount):
    """this utility deletes discount and revert prices of food"""
    prices = []
    for price in food.prices:
        prices.append(price * 100 // (100 - discount_amount))
    food.prices = prices
    food.min_price = min(prices)
    return food


def apply_discount(food, discount_amount):
    """this utility applies discount and sets new prices for food"""
    prices = []
    for price in food.prices:
        prices.append(price * (100 - discount_amount) // 100)
    food.prices = prices
    food.min_price = min(prices)
    return food


def get_vendor_key(id):
    return f"vendor:{id}:status"


def get_vendor_status(id):
    """this saves availability of vendor in redis"""
    key = get_vendor_key(id)
    status_raw = r.get(key)
    if not status_raw:
        r.set(key, dumps(True), 6 * 3600)
        return False
    return True
