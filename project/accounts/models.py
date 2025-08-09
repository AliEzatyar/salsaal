from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.contrib.gis.db import models as g_models
from django.contrib.gis.geos import Point
from django.utils import timezone
from django.conf import settings
import h3
ADMIN = 0
REST = 1
CUSTOMER = 2
CARRIER = 3

DEFAULT_OTP_EXPIRATION = 10  # minutes
FOOD_DELIVERY_OTP_EXPIRATION = 3 * 60  # 3 hours
CARRIER_ADD_OTP_EXPIRATION = 1440


# Create your models here.
class UserManager(BaseUserManager):
    def create_user(self, phone_number, email, full_name, password=None):

        email = self.normalize_email(email)
        if not phone_number:
            raise ValueError("phone_number_cannot_be_empty")
        if not full_name:
            raise ValueError("full_name_empty")
        user = self.model(
            phone_number=phone_number,
            full_name=full_name,
            email=email,
            password=password,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number: str, email, full_name, password=None):
        user = self.create_user(
            phone_number=phone_number,
            email=self.normalize_email(email),
            full_name=full_name,
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
    objects = UserManager()

    ROLE_CHOICES = [
        (ADMIN, "Admin"),
        (REST, "Resturant"),
        (CUSTOMER, "Customer"),
        (CARRIER, "Carrier"),
    ]

    full_name = models.CharField(max_length=60)
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

    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.phone_number

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_lable: str):
        return True


class UserProfile(g_models.Model):
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
        choices=settings.LANGUAGES,
    )
    country = models.CharField(max_length=2, choices=settings.COUNTRIES, default="AF")
    picture = models.ImageField(upload_to="users/pictures/", blank=True, null=True)
    address = models.CharField(blank=True, null=True, max_length=60)
    city = models.CharField(max_length=15)
    lattitude = models.CharField(max_length=20)
    longitude = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    location = g_models.PointField(null=True, blank=True, srid=4326)
    h3_id = models.CharField(max_length=55,blank=True,null=True)
    
    def __str__(self):
        return str(self.user)

    def save(self, *args, **kwargs):
        """overriding to set location point automatically"""
        if self.lattitude and self.longitude:
            self.location = Point(
                float(self.longitude), float(self.lattitude), srid=4326
            )
            self.h3_id = h3.latlng_to_cell(float(self.lattitude),float(self.longitude),res=9)
            
        return super().save(*args, **kwargs)

    def get_full_address(self):
        return self.address + ", " + self.city


class UserOtp(models.Model):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
    )
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self, expire=DEFAULT_OTP_EXPIRATION):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=expire)


class NoUserOtp(models.Model):
    phone_number = models.CharField(max_length=12)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self, expire=DEFAULT_OTP_EXPIRATION):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=expire)
