from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth import get_user_model
from marketplace.models import Product
from vendor.models import Vendor

User = get_user_model()


class Order(models.Model):
    STATUS_CHOICES = [
        (-1, "لغو"),
        (0, "تعلیق"),
        (1, "اجرا"),
        (2, "منتقل"),
        (3, "تحویل"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.SmallIntegerField(choices=STATUS_CHOICES, default=0)
    total_price = models.PositiveIntegerField(default=0)
    payment_id = models.CharField(max_length=250, blank=True, null= True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["-created"])]

    def __str__(self):
        return f"Order {self.id} - {self.user.username}"

    def calculate_total_price(self):
        self.total_price = sum(item.total_price for item in self.items.all())
        self.save()


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="order_items"
    )
    quantity = models.PositiveIntegerField()
    price = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.quantity} x {self.product.name} from {self.vendor.vendor_name}"

    @property
    def total_price(self):
        return self.quantity * self.price
