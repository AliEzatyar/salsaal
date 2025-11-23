from decimal import Decimal
from uuid import uuid4
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.utils import timezone as tz
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.postgres.indexes import GinIndex
from django.db.models import Q
# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    show_on_home = models.BooleanField(default=True)
    icon = models.ImageField(upload_to="categories-icons/", blank=True, null=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"
        ordering = ["-created_at"]

    @property
    def icon_url(self):
        try:
            return self.icon.url
        except ValueError:
            print("error: category has no icon")
            return None


    def __str__(self):
        return self.name


class Discount(models.Model):
    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, related_name="discounts"
    )
    amount = models.SmallIntegerField(
        default=0, validators=[MinValueValidator(1), MaxValueValidator(90)]
    )
    deadline = models.DateTimeField(default=tz.now) #!!!! should be date and hour
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]  # newest


class Food(models.Model):
    """please consider using decimal price value"""

    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )
    vendor = models.ForeignKey(
        "vendor.Vendor",
        on_delete=models.CASCADE,
        related_name="foods",
        db_index=True,
    )
    name = models.CharField(max_length=60, db_index=True)
    min_price = models.DecimalField(max_digits=6, decimal_places=1)
    prices = models.JSONField(default=list)
    category = models.ForeignKey(
        "marketplace.Category",
        on_delete=models.SET_NULL,
        null=True,
        related_name="foods",
        db_index=True,
    )
    image = models.ImageField(upload_to="foods-images/")
    description = models.TextField(max_length=250,blank=True,null=True)
    is_available = models.BooleanField(default=True, db_index=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    discount = models.ForeignKey(
        Discount, null=True, blank=True, on_delete=models.SET_NULL, related_name="foods"
    )
    is_featured = models.BooleanField(default=False)
    likes = models.IntegerField(default=0)
    is_drink = models.BooleanField(default=False)
    is_ready_type = models.BooleanField(default=False)
    ready_time = models.TimeField(null=True, blank=True)
    duration = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        verbose_name = "food"
        verbose_name_plural = "foods"
        ordering = ["-likes"]  # newest
        indexes = [
            GinIndex(
                name="food_name_trgm",
                fields=["name"],
                opclasses=["gin_trgm_ops"],
            ),
        ]
        constraints = [
            models.CheckConstraint(
                name="ready_or_duration_check",
                check=(
                    (
                        Q(is_ready_type=True)
                        & Q(ready_time__isnull=False)
                        & Q(duration__isnull=True)
                    )
                    | (
                        Q(is_ready_type=False)
                        & Q(duration__isnull=False)
                        & Q(duration__gt=0)
                        & Q(ready_time__isnull=True)
                    )
                ),
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk:
            # updated
            self.min_price = Decimal(min([float(x) for x in self.prices]))

        return super().save(*args, **kwargs)

    @property
    def image_url(self):
        try:
            return self.image.url
        except ValueError:
            print("error: food has no image")
            return None

    def __str__(self):
        return self.name



class Rating(models.Model):
    """rating models is used for both food and vendor models for now"""

    RATING_CHOICES = ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5))
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="+"
    )
    comment = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rating = models.PositiveSmallIntegerField(default=0, choices=RATING_CHOICES)
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE, null=True
    )
    modified_at = models.DateTimeField(auto_now=True)
    object_id = models.IntegerField(null=True)
    related_obj = GenericForeignKey("content_type", "object_id")
    enabled = models.BooleanField(default=True)

    @property
    def get_rating(self):
        return [i for i in range(self.rating)]


