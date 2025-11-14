from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    ForeignKey,
    DateTime,
    SmallInteger,
    DECIMAL,
    JSON,
    Time,
    Table,
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
from uuid import uuid4
from database import Base, engine, metadata
from sqlalchemy.orm import synonym
from sqlalchemy import Table

Base = declarative_base()

# load existing tables if needed


class Promotion(Base):
    """loads promotion table from db and enables ORM operations"""

    __tablename__ = "vendor_promotion"
    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey("vendor_vendor.id"))
    link = Column(String(60))
    image = Column(String(60))
    city = Column(String(60))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean)
    cost_per_day = Column(Integer)
    created_at = Column(DateTime)
    modified_at = Column(DateTime)
    vendor = synonym("vendor_id")


class Cart(Base):
    """loads cart table from db and enables ORM operations"""

    __table__ = Table("cart_cart", metadata, autoload_with=engine)


class Category(Base):
    """loads category table from db and enables ORM operations"""

    __tablename__ = "marketplace_category"
    id = Column(Integer, primary_key=True)
    name = Column(String(60))
    show_on_home = Column(Boolean, default=False)
    icon = Column(String)
    description = Column(String)
    created_at = Column(DateTime)
    foods = relationship("Food", back_populates="category_of")


# Many-to-many association for Vendor <-> OpeningHour
vendor_opening_hours = Table(
    "vendor_opening_hours",
    Base.metadata,
    Column("vendor_id", ForeignKey("vendor_vendor.id"), primary_key=True),
    Column("openinghour_id", ForeignKey("vendor_openinghour.id"), primary_key=True),
)


# ------------------ USER MODELS ------------------
class User(Base):
    __tablename__ = "accounts_user"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid4, unique=True, index=True)
    name = Column(String(60))
    email = Column(String(100), unique=True, nullable=True)
    phone_number = Column(String(12), unique=True)
    role = Column(SmallInteger, default=3)
    date_joined = Column(DateTime)
    modified_date = Column(DateTime)
    last_login = Column(DateTime)
    created_date = Column(DateTime)
    is_admin = Column(Boolean, default=False)
    is_staff = Column(Boolean, default=False)
    is_superadmin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=False)
    region = Column(String, default="AF")
    token_valid_after = Column(DateTime)

    vendor = relationship("Vendor", back_populates="user", uselist=False)
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="receiver")  # ✅ FIXED


class UserProfile(Base):
    __tablename__ = "accounts_userprofile"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid4, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("accounts_user.id"))
    pf_lang = Column(String(10), default="fa")
    country = Column(String(20), default="AF")
    picture = Column(String, nullable=True)
    address = Column(String(60), nullable=True)
    city = Column(String(15), index=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime)
    modified_at = Column(DateTime)
    location = Column(String, nullable=True)
    h3_id = Column(String(55), index=True, nullable=True)

    user = relationship("User", back_populates="profile")
    vendor = relationship("Vendor", back_populates="user_profile", uselist=False)


# ------------------ VENDOR MODELS ------------------
class Vendor(Base):
    __tablename__ = "vendor_vendor"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid4, unique=True, index=True)
    user_id = Column(Integer, ForeignKey("accounts_user.id"), unique=True, index=True)
    user_profile_id = Column(
        Integer, ForeignKey("accounts_userprofile.id"), unique=True, index=True
    )
    vendor_name = Column(String(60), unique=True, index=True)
    vendor_license = Column(String)
    vendor_type = Column(SmallInteger, default=1)
    image = Column(String)
    logo = Column(String)
    is_approved = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime)
    modified_at = Column(DateTime)
    avg_rating = Column(Float, default=0)
    rating_count = Column(SmallInteger, default=0)
    mfdd = Column(SmallInteger, default=0)
    mfcfd = Column(SmallInteger, nullable=True)
    min_order_price = Column(SmallInteger, default=100)
    delivery_fee_km = Column(SmallInteger, default=3)
    is_available = Column(Boolean, default=True)
    reward_percentage = Column(Float, default=0)

    user = relationship("User", back_populates="vendor")
    user_profile = relationship("UserProfile", back_populates="vendor")
    foods = relationship("Food", back_populates="vendor_of")
    discounts = relationship("Discount", back_populates="vendor")
    opening_hours = relationship(
        "OpeningHour", secondary=vendor_opening_hours, back_populates="vendors"
    )
    city = Column(String(20))
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    location = Column(String(60))
    h3_id = Column(String(60))
    is_open_now = synonym("is_available")


# ------------------ FOOD & DISCOUNT MODELS ------------------
class Food(Base):
    __tablename__ = "marketplace_food"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid4, unique=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendor_vendor.id"), index=True)
    name = Column(String(60), index=True)
    min_price = Column(DECIMAL(6, 1))
    prices = Column(JSON, default=[])
    category_id = Column(Integer, ForeignKey("marketplace_category.id"), index=True)
    image = Column(String)
    description = Column(String(250))
    is_available = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, index=True)
    modified_at = Column(DateTime)
    discount_id = Column(Integer, ForeignKey("marketplace_discount.id"), nullable=True)
    is_featured = Column(Boolean, default=False)
    likes = Column(Integer, default=0)
    is_drink = Column(Boolean, default=False)
    is_ready_type = Column(Boolean, default=False)
    ready_time = Column(Time, nullable=True)
    duration = Column(SmallInteger, nullable=True)
    vendor = synonym("vendor_id")
    vendor_of = relationship("Vendor", back_populates="foods")
    category_of = relationship("Category", back_populates="foods")
    category = synonym("category_id")
    discount = relationship("Discount", back_populates="foods")


class Discount(Base):
    __tablename__ = "marketplace_discount"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey("vendor_vendor.id"))
    amount = Column(SmallInteger, default=0)
    deadline = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime)
    vendor = relationship("Vendor", back_populates="discounts")
    foods = relationship("Food", back_populates="discount")


# ------------------ OPENING HOURS ------------------
class OpeningHour(Base):
    __tablename__ = "vendor_openinghour"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), default=uuid4, unique=True, index=True)
    start_hour = Column(Float, nullable=True)
    end_hour = Column(Float, nullable=True)
    weekday = Column(String, nullable=False)
    is_holiday = Column(Boolean, default=False)

    vendors = relationship(
        "Vendor", secondary=vendor_opening_hours, back_populates="opening_hours"
    )


# ------------------ NOTIFICATION ------------------
class Notification(Base):
    __tablename__ = "live_notification"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    receiver_id = Column(Integer, ForeignKey("accounts_user.id"), index=True)
    title = Column(String(255))
    type = Column(String(20))
    data = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime)
    target_id = Column(Integer, nullable=True)
    description = Column(String(255), nullable=True)

    receiver = relationship("User", back_populates="notifications")
