from math import sin, cos, radians, sqrt, atan2

from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis
from json import dumps as j_dumps, loads as j_loads
from settings import AWS_STORAGE_BUCKET_NAME, s3
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from models import Cart
from database import engine, metadata
from sqlalchemy import Table

# Autoload CartItem once (not ORM-mapped, just table reflection)
cart_item_table = metadata.tables.get("cart_cartitem")
if cart_item_table is None:
    cart_item_table = Table("cart_cartitem", metadata, autoload_with=engine)


DEFAULT_AVG_SPEED = 5


redis = aioredis.from_url(
    "redis://localhost:6379/2", encoding="utf-8", decode_responses=True
)
FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")


async def cache_set(key: str, value, ttl=600):
    await redis.set(key, j_dumps(value), ttl)
    return True


async def cache_get(key: str):
    value = await redis.get(key)
    if not value:
        return None
    return j_loads(value)


class BestVendorsCounter:
    """This class saves view counts and returns most viewed vendor IDs."""

    def __init__(self, city: str):
        self.redis = redis
        self.top_vendors_key = f"top_vendors:{city}:city"

    async def read_counts(self, max_results: int = 5):
        """Returns IDs of most viewed vendors in the city."""
        top = await self.redis.zrange(self.top_vendors_key, 0, -1, desc=True)
        top = top[:max_results]  # top vendors ids
        return [int(x) for x in top]


def get_total_cart_items(user_id: int) -> int:
    """Return total quantity of items in user's cart (fast, single SQL query)."""
    with Session(engine) as session:
        stmt = (
            select(func.coalesce(func.sum(cart_item_table.c.quantity), 0))
            .select_from(
                cart_item_table.join(
                    Cart.__table__, cart_item_table.c.cart_id == Cart.__table__.c.id
                )
            )
            .where(Cart.__table__.c.user_id == user_id)
        )
        return session.execute(stmt).scalar_one()


def haversine_distance(lat1, lon1, lat2, lon2):
    """this function estimates distance, 90 degree traingle, A-start, B , C-goal, then distance
    is b+c"""
    lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
    R = 6371  # Earth radius in kilometers

    phi1 = radians(lat1)
    phi2 = radians(lat2)

    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2

    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c  # distance in kilometers


def distance_to_travel_time(distance, avg_speed=DEFAULT_AVG_SPEED):
    return distance * 1000 / (avg_speed) / 60


def distance_reach_time(qs, lat, lon, typ="food"):

    for obj in qs:
        distance = round(
            haversine_distance(
                (obj.vendor_of.latitude if typ == "food" else obj.latitude),
                (obj.vendor_of.longitude if typ == "food" else obj.longitude),
                lat,
                lon,
            ),
            1,
        )
        if typ == "food":
            obj.discount_amount = obj.discount.amount
            obj.original_price = (obj.min_price / (100 - obj.discount.amount)) * 100
            obj.vendor_name = obj.vendor_of.vendor_name
            obj.category_name = obj.category_of.name
        obj.distance = distance
        obj.reach_time = round(distance_to_travel_time(distance))


def generate_image_url(key: str):
    """
    this utility generates the s3 url of an image
    key is the image short-address saved by django.
    """
    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": AWS_STORAGE_BUCKET_NAME, "Key": key},
    )
    return url


def set_image_url_to_scalars(qs, keyword="image"):
    """
    this utility sets s3 url to a collection of orm instances
    django by saves the partial address of image in database not full url,
    temporary urls should be generated using s3
    """
    if keyword == "vendor":
        for item in qs:
            item.image = generate_image_url(item.image)
            item.logo = generate_image_url(item.logo)
    elif keyword == "picture":
        for item in qs:
            item.picture = generate_image_url(item.picture)
    elif keyword == "image":
        for item in qs:
            item.image = generate_image_url(item.image)
