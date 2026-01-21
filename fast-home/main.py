from typing import Any
from fastapi import FastAPI
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import Depends, Request
from dependencies import get_db
from schemas import HomeSchema
from models import (
    Category,
    Discount,
    Food,
    Notification,
    Promotion,
    Vendor,
)
import geohash
from sqlalchemy import select
import h3
from utils import (
    CITIES_CENTER_POINTS,
    CITIES_DARI_TO_ENGLISH_NAMES_MAP,
    CITIES_ENGLISH_TO_DARI_NAMES_MAP,
    BestVendorsCounter,
    cache_get,
    cache_set,
    distance_reach_time,
    generate_image_url,
    get_total_cart_items,
    set_image_url_to_scalars,
    nearest_city
)
from schemas import CategorySchema
from auth import get_user, throttle_request

DEFAULT_H3_RESOLUTION = 9


app = FastAPI()

from typing import Optional
import h3


DEFAULT_CITY = "kabul"
DEFAULT_H3 = "8920905b437ffff"


@app.get("/api/marketplace/home/", response_model=HomeSchema)
async def home(
    request: Request,
    location: Optional[str] = None,
    city: Optional[str] = None,
    db: Session = Depends(get_db),
    user: Any = Depends(get_user),
):
    # ---------------- defaults
    city = (city or DEFAULT_CITY).lower()
    location = location or DEFAULT_H3

    # ---------------- decode H3 safely
    try:
        lat, lon = lat, lon = geohash.decode(location)
    except Exception as e :
        print("error decoding H3:", e)
        # last-resort fallback, because APIs should not rage-quit
        lat, lon = h3.cell_to_latlng(DEFAULT_H3)
        city = DEFAULT_CITY
    user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
    
    is_foreign = False
    # if persian city name given, convert to english
    if city in CITIES_DARI_TO_ENGLISH_NAMES_MAP.keys():
        city = CITIES_DARI_TO_ENGLISH_NAMES_MAP[city]
    # foreign city name given, alter home data to only online vendors
    if not city in CITIES_ENGLISH_TO_DARI_NAMES_MAP.keys():
        is_foreign = True
        city = DEFAULT_CITY
        user_h3 = DEFAULT_H3
        
    if not city in [i[0] for i in CITIES_CENTER_POINTS]:
        city = nearest_city(lat,lon)
    
    # ---------------- counters
    user_notf_count = 0
    user_cart_count = 0

    # ---------------- throttle
    if not user:
        if not await throttle_request(http_request=request):
            return {"detail": "Too many requests, please try later."}
    else:
        if not await throttle_request(user_id=user.id):
            return {"detail": "Too many requests, please try later."}

        user_notf_count = (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.receiver_id == user.id,
                    Notification.is_read.is_(False),
                )
            )
            or 0
        )
        user_cart_count = get_total_cart_items(user.id)

    # ---------------- categories
    categories_key = "categories_all"
    categories = await cache_get(categories_key)
    if not categories:
        categories_q = db.query(Category).all()
        categories = [
            CategorySchema.model_validate(c).model_dump() for c in categories_q
        ]
        for cat in categories:
            cat["icon"] = generate_image_url(cat["icon"])
        await cache_set(categories_key, categories)

    # ---------------- city vendors
    city_vendor_ids_key = f"vdrs:{city}:ids"
    city_vendor_ids = await cache_get(city_vendor_ids_key)
    if is_foreign:
        city = DEFAULT_CITY
        
        
        ids = (
            db.query(Vendor.id)
            .filter(Vendor.city == city, Vendor.hesabpay_number != None, Vendor.is_approved.is_(True))
            .all()
        )
        city_vendor_ids = [v.id for v in ids]
    if not city_vendor_ids:
        ids = (
            db.query(Vendor.id)
            .filter(Vendor.city == city, Vendor.is_approved.is_(True))
            .all()
        )
        city_vendor_ids = [v.id for v in ids]
        await cache_set(city_vendor_ids_key, city_vendor_ids)
    
    # ---------------- city foods
    city_foods_ids_key = f"foods:{city}:ids"
    city_foods_ids = await cache_get(city_foods_ids_key)
    if not city_foods_ids:
        ids = (
            db.query(Food.id)
            .join(Vendor)
            .filter(Vendor.city == city)
            .all()
        )
        city_foods_ids = [v.id for v in ids]
        await cache_set(city_foods_ids_key, city_foods_ids)

    city_vendors_qs = select(Vendor).where(Vendor.id.in_(city_vendor_ids))
    city_foods_qs = select(Food).where(Food.id.in_(city_foods_ids))

    # ---------------- promotions
    promotions = db.scalars(
        select(Promotion).where(Promotion.city == city)
    ).all()
    set_image_url_to_scalars(promotions, "image")

    # ---------------- discounted foods
    discounted_foods = db.scalars(
        city_foods_qs.join(Discount).where(Discount.is_active.is_(True))
    ).all()
    set_image_url_to_scalars(discounted_foods, "image")
    distance_reach_time(discounted_foods, lat, lon, "food")

    # ---------------- local vendors (H3 grid)
    nearest_h3s = h3.grid_disk(user_h3,20)

    local_vendors = db.scalars(
        city_vendors_qs.where(Vendor.h3_id.in_(nearest_h3s))
    ).all()
    set_image_url_to_scalars(local_vendors, "vendor")
    distance_reach_time(local_vendors, lat, lon, "vendor")

    # ---------------- cheapest vendors
    cheapest_vendors = db.scalars(
        city_vendors_qs.join(Food)
        .group_by(Vendor.id)
        .order_by(func.avg(Food.min_price))
        .limit(10)
    ).all()
    set_image_url_to_scalars(cheapest_vendors, "vendor")
    distance_reach_time(cheapest_vendors, lat, lon, "vendor")

    # ---------------- top vendors
    counter = BestVendorsCounter(city)
    top_vendors_ids = await counter.read_counts()
    top_vendors = db.scalars(
        city_vendors_qs.where(Vendor.id.in_(top_vendors_ids))
        .order_by(func.random())
    ).all()
    set_image_url_to_scalars(top_vendors, "vendor")

    return {
        "cart_count": user_cart_count,
        "notf_count": user_notf_count,
        "categories": categories,
        "promotions": promotions,
        "discounted_foods": discounted_foods,
        "local_vendors": local_vendors,
        "cheapest_vendors": cheapest_vendors,
        "top_vendors": top_vendors,
    }
