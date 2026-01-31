from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class CategorySchema(BaseModel):
    id: int
    name: str
    icon: str
    model_config = ConfigDict(from_attributes=True)


class VendorBase(BaseModel):
    id: int
    vendor_name: str
    avg_rating: float
    rating_count: int
    image: Optional[str] = None
    logo: Optional[str] = None
    vendor_type: Optional[int] = None
    is_open_now: bool


class VendorOut(VendorBase):
    distance: Optional[float] = None
    reach_time: Optional[int] = None  # e.g., in minutes

    class Config:
        from_attributes = True


class FoodSchema(BaseModel):
    id: int
    name: str


class PromotionSchema(BaseModel):
    vendor: Optional[int]
    image: str
    link: str


class DiscountedFoodsSchema(BaseModel):
    id: int
    name: str
    image: str
    original_price: Decimal
    discount_amount: Optional[int]
    min_price: Decimal
    vendor: int
    vendor_name: str
    category: int
    reach_time: Optional[int]
    distance: Optional[float]
    likes: int
    category_name: str


class HomeSchema(BaseModel):
    cart_count: Optional[int] = None
    notf_count: Optional[int] = None
    categories: Optional[List[CategorySchema]] = None
    promotions: Optional[List[PromotionSchema]] = None
    discounted_foods: Optional[List[DiscountedFoodsSchema]] = None
    local_vendors: Optional[List[VendorOut]] = None
    cheapest_vendors: Optional[List[VendorOut]] = None
    top_vendors: Optional[List[VendorOut]] = None
