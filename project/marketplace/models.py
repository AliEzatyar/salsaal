from django.db import models


from django.db import models
from vendor.utils import slugify_persian

# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
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
        "vendor.Vendor", on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=6, decimal_places=0)
    inventory = models.IntegerField(choices=INVENTORY_CHOICES)
    category = models.ForeignKey(
        "marketplace.Category", on_delete=models.CASCADE, related_name="products"
    )
    description = models.TextField(max_length=250, blank=True, null=True)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True)
    is_available = models.BooleanField(default=True)
    modified = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "product"
        verbose_name_plural = "products"
        ordering = ["-modified"]

    def save(self, *args, **kwargs):
        """overriding for slugifying the name field"""
        self.slug = slugify_persian(self.name)
        return super().save()

    def __str__(self):
        return self.name
