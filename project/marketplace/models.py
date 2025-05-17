from decimal import Decimal
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from django.contrib.contenttypes.models import ContentType
# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    show_on_home = models.BooleanField(default=True)

    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Food(models.Model):
    """please consider using decimal price value"""

    vendor = models.ForeignKey(
        "vendor.Vendor",
        on_delete=models.CASCADE,
        related_name="foods",
        db_index=True,
    )
    name = models.CharField(max_length=60, db_index=True)
    min_price = models.DecimalField(max_digits=6, decimal_places=2)
    prices = models.JSONField(default=list)
    category = models.ForeignKey(
        "marketplace.Category",
        on_delete=models.CASCADE,
        related_name="foods",
        db_index=True,
    )
    # price options ???????
    description = models.TextField(max_length=250)
    image = models.ImageField(upload_to="foods/")
    is_available = models.BooleanField(default=True, db_index=True)
    modified_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    avg_rating = models.PositiveSmallIntegerField(default=0)
    rating_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "food"
        verbose_name_plural = "foods"
        ordering = ["-modified_at"]  # newest
        unique_together = ['name',"vendor"]

    def update_avg_rating(self, *args, **kwargs):
        ct = ContentType.objects.get_for_model(Food)
        avg_and_count = Rating.objects.filter(
            object_id=self.pk,
            content_type=ct,
        ).aggregate(avg=models.Avg("rating"), count=models.Count("rating"))
        self.avg_rating = avg_and_count["avg"] or 0.0
        self.rating_count = avg_and_count["count"] or 0
        self.save()

    def save(self, *args, **kwargs):
        if self.pk:
            # updated
            self.min_price = Decimal(min([float(x) for x in self.prices]))

        return super().save(*args, **kwargs)

    def __str__(self):
        print(self.prices)
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
    object_id = models.IntegerField(null=True)
    related_obj = GenericForeignKey("content_type", "object_id")
    enabled = models.BooleanField(default=True)

    @property
    def get_rating(self):
        return [i for i in range(self.rating)]


class FavList(models.Model):
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="favlist"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def total_items(self):
        return self.items.count()

    def __str__(self):
        return f"FavList <{self.user.username}>"


class FavItem(models.Model):
    favlist = models.ForeignKey(
        "marketplace.FavList", on_delete=models.CASCADE, related_name="items"
    )
    food = models.ForeignKey(
        "marketplace.Food", on_delete=models.CASCADE, related_name="+"
    )
