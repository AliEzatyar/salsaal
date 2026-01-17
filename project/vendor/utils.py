from asyncio.log import logger
from json import dumps
from marketplace.utils import r
from logging import getLogger   
from re import sub

logger = getLogger(__name__)

def to_af_weekday(index):
    return (9 + index) % 7 + 1

def normalize_phone(number: str, local_length: int = 9) -> str:
    # keep digits only
    digits = sub(r"\D", "", number)

    # keep last N digits (local number)
    return digits[-local_length:]


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


