from datetime import timedelta
from uuid import uuid4
from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.contrib.gis.db import models as g_models
from django.contrib.gis.geos import Point
from h3 import latlng_to_cell as h3_latlng_to_cell
from django.utils import timezone
from django.contrib.auth import get_user_model
from marketplace.utils import DEFAULT_H3_RESOLUTION

ADMIN = 0
REST = 1
CUSTOMER = 2
CARRIER = 3

DEFAULT_OTP_EXPIRATION = 10  # minutes
FOOD_DELIVERY_OTP_EXPIRATION = 3 * 60  # 3 hours
CARRIER_ADD_OTP_EXPIRATION = 1440
OTP_RETRY_DELAY = 600
DEFAULT_CITY = "kabul"


def get_token_valid_after():
    """
    this helper is used to get default token valid after datetime,
    it is also used in login and sign up to update token validation
    """
    return timezone.now() - timedelta(seconds=5)


# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, phone_number, email, name, password=None):

        email = self.normalize_email(email)
        if not phone_number:
            raise ValueError("phone_number_cannot_be_empty")
        if not name:
            raise ValueError("name_empty")
        user = self.model(
            phone_number=phone_number,
            name=name,
            email=email,
            password=password,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number: str, email, name, password=None):
        user = self.create_user(
            phone_number=phone_number,
            email=self.normalize_email(email),
            name=name,
            password=password,
        )

        user.set_password(password)
        user.is_admin = True
        user.is_staff = True
        user.is_active = True
        user.is_superadmin = False
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )

    objects = UserManager()
    token_valid_after = models.DateTimeField(default=get_token_valid_after)
    ROLE_CHOICES = [
        (ADMIN, "Admin"),
        (REST, "Resturant"),
        (CUSTOMER, "Customer"),
        (CARRIER, "Carrier"),
    ]

    name = models.CharField(max_length=60)
    email = models.EmailField(max_length=100, unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=12, unique=True)
    role = models.PositiveSmallIntegerField(
        choices=ROLE_CHOICES, blank=True, default=CUSTOMER
    )

    # django required fields
    date_joined = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now_add=True)
    created_date = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superadmin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    region = models.CharField(blank=True, null=True, default="AF")

    USERNAME_FIELD = "phone_number"

    REQUIRED_FIELDS = ["name","email"]

    def __str__(self):
        return self.phone_number

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_lable: str):
        return True


class UserProfile(g_models.Model):
    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="profile",
    )
    pf_lang = models.CharField(
        max_length=10,
        default="fa",
    )
    country = models.CharField(max_length=20, default="AF")
    picture = models.ImageField(upload_to="users/pictures/", blank=True, null=True)
    address = models.CharField(blank=True, null=True, max_length=60)
    city = models.CharField(max_length=15, db_index=True)
    latitude = models.CharField(max_length=20, blank=True, null=True)
    longitude = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    location = g_models.PointField(null=True, blank=True, srid=4326)
    h3_id = models.CharField(max_length=55, blank=True, null=True, db_index=True)
            
    def __str__(self):
        return str(self.user)

    def save(self, *args, **kwargs):
        """overriding to set location point automatically"""
        if self.latitude and self.longitude:
            self.location = Point(
                float(self.longitude), float(self.latitude), srid=4326
            )
            self.h3_id = h3_latlng_to_cell(
                float(self.latitude), float(self.longitude), DEFAULT_H3_RESOLUTION
            )
            self.city = str(self.city).lower()

        return super().save(*args, **kwargs)

    def get_full_address(self):
        return self.address + ", " + self.city


class Device(models.Model):
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="devices", blank=True
    )
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserOtp(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, db_index=True)
    otp = models.CharField(max_length=8, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self, expire=DEFAULT_OTP_EXPIRATION):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=expire)


class NoUserOtp(models.Model):
    phone_number = models.CharField(max_length=12)
    otp = models.CharField(max_length=6, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self, expire=DEFAULT_OTP_EXPIRATION):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=expire)
