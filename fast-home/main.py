from typing import Any
from fastapi import FastAPI
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import Depends
from dependencies import get_db
from schemas import HomeSchema
from models import (
    Category,
    Discount,
    Food,
    Notification,
    Promotion,
    User,
    Vendor,
)
import geohash
from sqlalchemy import select
import h3
from utils import (
    BestVendorsCounter,
    cache_get,
    cache_set,
    distance_reach_time,
    generate_image_url,
    get_total_cart_items,
    set_image_url_to_scalars,
)
from schemas import CategorySchema
from auth import get_user

DEFAULT_H3_RESOLUTION = 9


app = FastAPI()


@app.get("/api/marketplace/home/", response_model=HomeSchema)
async def home(
    location: str,
    city: str,
    db: Session = Depends(get_db),
    user : Any = Depends(get_user)
):
    # ----------- user cart and notf count if auth provided
    user_notf_count = 0
    user_cart_count = 0
    if user:
        user_notf_count = (
            db.scalar(
                select(Notification.id).where(
                    Notification.receiver_id == user.id, Notification.is_read == False
                )
            )
            or 0
        )
        user_cart_count = get_total_cart_items(user.id)
    # --------------- decoding location and getting city
    try:
        lat, lon = geohash.decode(location)
        city = str(city).lower()
    except Exception as e:
        return {
            "cart_count": 0,
            "notf_count": 0,
            "categories": [],
            "promotions": [],
            "discounted_foods": [],
            "local_vendors": [],
            "cheapest_vendors": [],
            "top_vendors": [],
        }

    # ----------- categories
    categories_key = "categories_all"
    categories = await cache_get(categories_key)
    if not categories:
        categories_q = db.query(Category).all()
        # converting to dict so to be able to cache
        categories = [
            CategorySchema.model_validate(c).model_dump() for c in categories_q
        ]
        for cat in categories:
            cat["icon"] = generate_image_url(cat["icon"])
        await cache_set(categories_key, categories)
    # ------------ city_vendors
    city_vendor_ids_key = f"vdrs:{city}:ids"
    city_vendor_ids = await cache_get(city_vendor_ids_key)
    if not city_vendor_ids:
        ids = db.query(Vendor.id).filter(Vendor.city == city,Vendor.is_approved==True).all()
        city_vendor_ids = [v.id for v in ids]
        await cache_set(city_vendor_ids_key, city_vendor_ids)
    # ------------ city foods
    city_foods_ids_key = f"foods:{city}:ids"
    city_foods_ids = await cache_get(city_foods_ids_key)
    if not city_foods_ids:
        ids = db.query(Food.id).join(Vendor).filter(Vendor.city == city).all()
        city_foods_ids = [v.id for v in ids]
        await cache_set(city_foods_ids_key, city_foods_ids)
    # -------- creating reusable stmt for city vendors and foods
    city_vendors_qs = select(Vendor).filter(Vendor.id.in_(city_vendor_ids))
    city_foods_qs = select(Food).where(Food.id.in_(city_foods_ids))
    # promotions
    promotions_qs = select(Promotion).where(Promotion.city == city)
    promotions = db.scalars(promotions_qs).all()
    set_image_url_to_scalars(promotions, "image")
    # discounted foods
    discounted_foods_qs = city_foods_qs.join(
        Discount, Discount.id == Food.discount_id
    ).where(Discount.is_active == True)
    discounted_foods = db.scalars(discounted_foods_qs).all()
    set_image_url_to_scalars(discounted_foods, "image")
    distance_reach_time(discounted_foods, lat, lon, "food")
    # local vendors
    user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
    nearest_h3s = h3.grid_disk(user_h3, 10)
    local_vendors = db.scalars(
        city_vendors_qs.where(Vendor.h3_id.in_(nearest_h3s))
    ).all()
    set_image_url_to_scalars(local_vendors, "vendor")
    distance_reach_time(local_vendors, lat, lon, "vendor")
    # cheapest_vendors
    cheapest_vendors_qs = (
        city_vendors_qs.join(Food, Food.vendor_id == Vendor.id)
        .add_columns(func.avg(Food.min_price).label("avg_price"))
        .group_by(Vendor.id)
        .order_by(func.avg(Food.min_price))
        .limit(10)
    )
    cheapest_vendors = db.scalars(cheapest_vendors_qs).all()
    set_image_url_to_scalars(cheapest_vendors, "vendor")
    distance_reach_time(cheapest_vendors, lat, lon, "vendor")
    # top vendors
    counter = BestVendorsCounter(city)
    top_vendors_ids = await counter.read_counts()
    top_vendors = db.scalars(
        city_vendors_qs.filter(Vendor.id.in_(top_vendors_ids)).order_by(func.random())
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
