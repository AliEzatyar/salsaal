from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models
from vendor.utils import slugify_persian
from django.template.loader import render_to_string

# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(max_length=250, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True)

    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"
        ordering = ["-modified"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """overriding for slugifying the name field"""
        self.slug = slugify_persian(self.name)
        return super().save()


class Product(models.Model):
    INVENTORY_CHOICES = [(1, "پل خشک-کابل"), (2, "قلعه نو-کابل"), (3, "پل سوخته-کابل")]

    vendor = models.ForeignKey(
        "vendor.Vendor",
        on_delete=models.CASCADE,
        related_name="products",
        db_index=True,
    )
    name = models.CharField(max_length=60, db_index=True)
    price = models.DecimalField(max_digits=6, decimal_places=0, db_index=True)
    inventory = models.IntegerField(choices=INVENTORY_CHOICES)
    category = models.ForeignKey(
        "marketplace.Category",
        on_delete=models.CASCADE,
        related_name="products",
        db_index=True,
    )
    description = models.TextField(max_length=250, blank=True, null=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    slug = models.SlugField(
        max_length=100, unique=True, blank=True, null=True, db_index=True
    )
    is_available = models.BooleanField(default=True, db_index=True)
    modified = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    existing_amount = models.PositiveSmallIntegerField(default=1)
    sold_amount = models.PositiveSmallIntegerField(default=0)
    rating = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "product"
        verbose_name_plural = "products"
        ordering = ["-modified"]

    def save(self, *args, **kwargs):
        """overriding for slugifying the name field"""
        self.slug = slugify_persian(self.name)
        return super().save()

    def rating_form(self):
        html = render_to_string(
            "marketplace/rating_form.html",
            context={"object_id": self.pk, "type": "product"},
        )
        return html

    def overall_rating(self):
        """this utility method returns the rating average"""
        ratings = Rating.objects.filter(object_id=self.pk).values_list('rating')
        ratings = [r[0] for r in ratings]
        if len(ratings) == 0:
            return 0
        self.rating = sum(ratings) / len(ratings)
        self.save()
        return sum(ratings)/len(ratings)

    def __str__(self):
        return self.name


class Rating(models.Model):
    """rating models is used for both product and vendor models for now"""

    RATING_CHOICES = ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5))
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="+"
    )
    comment = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    rating = models.PositiveSmallIntegerField(default=0, choices=RATING_CHOICES)
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.IntegerField()
    related_obj = GenericForeignKey("content_type", "object_id")

    @property
    def get_rating(self):
        return [i for i in range(self.rating)]

    def save(self, *args, **kwargs):
        """overriding it to avoid duplicate rating"""
        previous = Rating.objects.filter(
            user=self.user, object_id=self.object_id
        ).first()
        # preventing recursion when existing before
        if previous and not 'update_fields' in kwargs:
            """overriding new"""
            print("existing....")
            previous.comment = self.comment
            previous.rating = self.rating
            previous.save(update_fields=['comment','rating'])
        else:
            return super().save(*args, **kwargs)
