import time
from fastapi import FastAPI
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import Depends
from auth import get_user
from dependencies import get_db
from schemas import ListCategorySchema
from models import Category, Discount, Food, Notification, Promotion, User, UserProfile, Vendor
import geohash
from sqlalchemy import select
import h3
from utils import BestVendorsCounter, cache_get, cache_set, distance_reach_time, get_total_cart_items

DEFAULT_H3_RESOLUTION = 9

from schemas import CategorySchema

app = FastAPI()


@app.get("/api/marketplace/home/", response_model=ListCategorySchema)
async def home(
    location: str,
    city: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
):
    # decoding location
    try:
        lat, lon = geohash.decode(location)
    except Exception as e:
        print("error occured while decoding location", e)
        return {}
    city = city.lower()
    # ----------- user cart and notf count
    user_notf_count = db.scalar(
        select(Notification.id)
        .where(Notification.receiver_id == user.id, Notification.is_read == False)
    )
    user_cart_count = get_total_cart_items(user.id)
    print(user_notf_count,user_cart_count)
    # ----------- categories
    categories_key = "categories_all"
    categories = await cache_get(categories_key)
    if not categories:
        categories_q = db.query(Category).all()
        # converting to dict so to be able to cache
        categories = [
            CategorySchema.model_validate(c).model_dump() for c in categories_q
        ]
        await cache_set(categories_key, categories)
    # ------------ city_vendors
    city_vendor_ids_key = f"vdrs:{city}:ids"
    city_vendor_ids = await cache_get(city_vendor_ids_key)
    if not city_vendor_ids:
        ids = (
            db.query(Vendor.id).join(UserProfile).filter(UserProfile.city == city).all()
        )
        city_vendor_ids = [v.id for v in ids]
        await cache_set(city_vendor_ids_key, city_vendor_ids)
    # ------------ city foods
    city_foods_ids_key = f"foods:{city}:ids"
    city_foods_ids = await cache_get(city_foods_ids_key)
    if not city_foods_ids:
        ids = (
            db.query(Food.id)
            .join(Vendor)
            .join(UserProfile)
            .filter(UserProfile.city == city)
            .all()
        )
        city_foods_ids = [v.id for v in ids]
        await cache_set(city_foods_ids_key, city_foods_ids)
    # -------- creating reusable stmt for city vendors and foods
    city_vendors_qs = (
        select(Vendor).join(UserProfile).filter(Vendor.id.in_(city_vendor_ids))
    )
    city_foods_qs = select(Food).where(Food.id.in_(city_foods_ids))
    # promotions
    promotions_qs = select(Promotion).where(Promotion.city == city)
    promotions = db.scalars(promotions_qs).all()
    # discounted foods
    discounted_foods_qs = (
        city_foods_qs.join(Discount, Discount.id == Food.discount_id)
        .where(Discount.is_active == True)
        .add_columns()
    )
    discounted_foods = db.scalars(discounted_foods_qs).all()
    distance_reach_time(discounted_foods, lat, lon, "food")
    # local vendors
    user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
    nearest_h3s = h3.grid_disk(user_h3, 10)
    local_vendors = db.scalars(
        city_vendors_qs.where(UserProfile.h3_id.in_(nearest_h3s))
    ).all()
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
    distance_reach_time(cheapest_vendors, lat, lon, "vendor")
    # top vendors
    counter = BestVendorsCounter(city)
    top_vendors_ids = await counter.read_counts()
    top_vendors = db.scalars(
        city_vendors_qs.filter(Vendor.id.in_(top_vendors_ids))
    ).all()
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
