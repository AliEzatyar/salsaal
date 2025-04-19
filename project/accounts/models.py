from django.db import models
from django.contrib.auth.models import BaseUserManager, AbstractBaseUser
from django.contrib.gis.db import models as g_models
from django.contrib.gis.geos import Point
from django.utils import timezone

SHOP = 1
CUSTOMER = 2
CARRIER = 3

DEFAULT_OTP_EXPIRATION = 10 # minutes
FOOD_OTP_EXPIRATION = 1440 # 1 Day
# Create your models here.
class UserManager(BaseUserManager):
    def create_user(
        self, first_name: str, last_name: str, username: str, email, password=None
    ):
        email = self.normalize_email(email)
        if not username:
            raise ValueError("username cannot be empty")
        if not email:
            raise ValueError("email cannot be empty")

        user = self.model(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, first_name: str, last_name: str, username: str, email, password=None
    ):
        user = self.create_user(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=self.normalize_email(email),
        )

        user.set_password(password)
        user.save(using=self._db)
        user.is_admin = True
        user.is_staff = True
        user.is_active = True
        user.is_superadmin = False
        user.save(using=self._db)

        return user


class User(AbstractBaseUser):
    objects = UserManager()

    ROLE_CHOICES = [
        (SHOP, "Shop"),
        (CUSTOMER, "Customer"),
        (CARRIER, "Carrier"),
    ]

    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    username = models.CharField(max_length=60, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    phone_number = models.CharField(
        max_length=12,
        blank=True,
    )
    role = models.PositiveSmallIntegerField(choices=ROLE_CHOICES, blank=True, null=True)

    # django required fields
    date_joined = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now_add=True)
    created_date = models.DateTimeField(auto_now_add=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_superadmin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_lable: str):
        return True

    def get_role(self):
        role = "Customer"
        if self.role == 1:
            role = "Shop"
        return role


class UserProfile(g_models.Model):
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="profile",
    )
    picture = models.ImageField(upload_to="users/pictures/", blank=True, null=True)
    cover = models.ImageField(upload_to="users/covers/", blank=True, null=True)
    address = models.CharField(blank=True, null=True, max_length=60)
    city = models.CharField(max_length=15, blank=True, null=True)
    lattitude = models.CharField(max_length=20, blank=True, null=True)
    longtitiude = models.FloatField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    phone = models.CharField(max_length=12, null=True, blank=True)
    location = g_models.PointField(null=True, blank=True, srid=4326)

    def __str__(self):
        return str(self.user)

    def save(self, *args, **kwargs):
        if self.lattitude and self.longtitiude:
            self.location = Point(float(self.longtitiude), float(self.lattitude))
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
    
    def is_expired(self,expire=DEFAULT_OTP_EXPIRATION):
        return timezone.now() > self.created_at + timezone.timedelta(
            minutes=expire
        )
