from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class CategorySchema(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)

class VendorBase(BaseModel):
    id: int
    vendor_name: str
    avg_rating: float
    rating_count: int
    image: Optional[str] = None
    logo: Optional[str] = None
    vendor_type: Optional[int] = None


class VendorOut(VendorBase):
    distance: Optional[float] = None
    reach_time: Optional[int] = None  # e.g., in minutes
    is_open_now: Optional[bool] = None

    class Config:
        orm_mode = True


class FoodSchema(BaseModel):
    id: int
    name: str


class PromotionSchema(BaseModel):
    id: int
    image: str
    link: str


class DiscountedFoodsSchema(BaseModel):
    id: int
    name: str
    image: str
    min_price: Decimal
    discount_amount: Optional[int]
    reach_time: Optional[int]
    distance: Optional[float]
    # "final_price",
    # "vendor",
    # "vendor_name",
    # "category",
    # "likes",
    # "category_name",


class ListCategorySchema(BaseModel):
    cart_count: int
    notf_count: int
    categories: List[CategorySchema]
    promotions: List[PromotionSchema]
    discounted_foods: List[DiscountedFoodsSchema]
    local_vendors: List[VendorOut]
    cheapest_vendors: List[VendorOut]
    top_vendors : List[VendorOut]
