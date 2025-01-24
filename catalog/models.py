from django.db import models

from vendor.models import Vendor

# Create your models here.


class Category(models.Model):
    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, related_name="categories",default=Vendor.objects.first().id
    )

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(max_length=250, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True)

    class Meta:
        verbose_name = "category"
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=60)
    price = models.DecimalField(max_digits=6, decimal_places=0)
    inventory = models.IntegerField()
    category = models.ForeignKey(
        "catalog.Category", on_delete=models.PROTECT, related_name="products"
    )
    description = models.TextField(max_length=250, blank=True, null=True)
    image = models.ImageField(upload_to="products/")
    slug = models.SlugField(max_length=100, unique=True, blank=True, null=True)
    is_available = models.BooleanField(default=True)
    modified = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "product"
        verbose_name_plural = "products"

    def __str__(self):
        return self.title
