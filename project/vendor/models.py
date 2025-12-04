from uuid import uuid4
from django.db import models
from accounts.models import DEFAULT_CITY, User, UserProfile
from live.utils import send_notification
from marketplace.models import Rating
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.indexes import GinIndex
from django.utils.timezone import now
from django.contrib.gis.db import models as g_models
from django.contrib.gis.geos import Point
from h3 import latlng_to_cell as h3_latlng_to_cell
from marketplace.utils import DEFAULT_H3_RESOLUTION
from django.utils.translation import activate, deactivate, gettext as _


# Create your models here.
VENDOR_TYPES = [
    (1, "restaurant"),
    (2, "coffeshop"),
    (3, "juiceshop"),
]


class Vendor(models.Model):

    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="vendor",
        db_index=True,
        unique=True,
    )
    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="vendor",
        db_index=True,
        unique=True,
    )
    vendor_name = models.CharField(max_length=60, unique=True, db_index=True)
    vendor_license = models.ImageField(upload_to="vendor/license/")
    vendor_type = models.PositiveSmallIntegerField(choices=VENDOR_TYPES, default=1)
    image = models.ImageField(upload_to="vendor/image/")
    logo = models.ImageField(upload_to="vendor/logo/")
    is_approved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    license_valid_until = models.DateField(auto_now_add=True)
    avg_rating = models.FloatField(default=0)
    rating_count = models.PositiveSmallIntegerField(default=0)
    opening_hours = models.ManyToManyField(
        to="vendor.OpeningHour", related_name="vendors"
    )
    mfdd = models.PositiveSmallIntegerField(
        default=0, blank=True
    )  # max free distance delivery
    mfcfd = models.PositiveSmallIntegerField(
        null=True, blank=True
    )  # min food count free delivery
    min_order_price = models.PositiveSmallIntegerField(default=100)  # AFS
    delivery_fee_km = models.PositiveSmallIntegerField(
        default=3
    )  # delivery fee per km AFS
    is_available = models.BooleanField(default=True)
    reward_percentage = models.FloatField(default=0)
    latitude = models.FloatField()
    longitude = models.FloatField()
    location = g_models.PointField(null=True, blank=True, srid=4326)
    h3_id = models.CharField(max_length=55, blank=True)
    city = models.CharField(max_length=15, db_index=True)
    hesabpay_number = models.CharField(max_length=30, blank=True, null=True)
    
    class Meta:

        ordering = ["-avg_rating"]
        indexes = [
            GinIndex(
                name="vendor_name_trgm",
                fields=["vendor_name"],
                opclasses=["gin_trgm_ops"],
            ),
        ]

    def __str__(self):
        return self.vendor_name

    def update_avg_rating(self, *args, **kwargs):
        """this method updates vendor avg_rating after a new rating is created"""
        ct = ContentType.objects.get_for_model(Vendor)
        avg_and_count = Rating.objects.filter(
            object_id=self.pk,
            content_type=ct,
        ).aggregate(avg=models.Avg("rating"), count=models.Count("rating"))
        self.avg_rating = avg_and_count["avg"] or 0.0
        self.rating_count = avg_and_count["count"] or 0
        self.save()

    def save(self, *args, **kwargs):
        """overriding to send approve email and save location"""
        # admin updates this vendor
        if self.pk != None:
            # update happend
            obj = Vendor.objects.get(pk=self.pk)
            if not obj.is_approved:
                if self.is_approved:
                    # vendor got approved
                    activate(obj.user_profile.pf_lang)
                    send_notification(
                        self.user.id,
                        _("Congratulations! Your vendor account has been approved."),
                        _("Congratulations! Your vendor account '{self.vendor_name}' has been approved.").format(self=self),
                        
                    )
                    deactivate()                
        # vendor update/saves this
        if self.latitude and self.longitude:
            self.location = Point(
                self.longitude, self.latitude, srid=4326
            )
            self.h3_id = h3_latlng_to_cell(
                self.latitude, self.longitude, DEFAULT_H3_RESOLUTION
            )

        return super(Vendor, self).save(*args, **kwargs)

    @property
    def image_url(self):
        try:
            return self.image.url
        except ValueError:
            print("vendor has no image")
            return None

    @property
    def logo_url(self):
        try:
            return self.logo.url
        except ValueError:
            return None


HOURS = [(i + add, i + add) for i in range(24) for add in (0,)]
WEEKDAYS = [
    ("1", "Saturday"),
    ("2", "Sunday"),
    ("3", "Monday"),
    ("4", "Tuesday"),
    ("5", "Wednesday"),
    ("6", "Thursday"),
    ("7", "Friday"),
]


class OpeningHour(models.Model):
    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )
    start_hour = models.FloatField(choices=HOURS, null=True)
    end_hour = models.FloatField(choices=HOURS, null=True)
    weekday = models.CharField(choices=WEEKDAYS)
    is_holiday = models.BooleanField(default=False)

    def __str__(self):
        return self.weekday + "-" + str(self.start_hour) + "-" + str(self.end_hour)


class Promotion(models.Model):
    """this model resembles promotional images at home page"""

    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, null=True, blank=True
    )
    link = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to="promotions/")
    city = models.CharField(default="kabul", max_length=20)
    start_date = models.DateTimeField(default=now)
    end_date = models.DateTimeField(default=now)
    is_active = models.BooleanField(default=False)
    cost_per_day = models.PositiveSmallIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
