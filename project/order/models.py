from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth import get_user_model
from marketplace.models import Food
from vendor.models import Vendor

User = get_user_model()

ORDER_STATUS_CHOICES = [
    ("cancelled", "cancelled"),
    ("waiting", "waiting"),
    ("preparing", "preparing"),
    ("carrying", "carrying"),
    ("delivered", "delivered"),
]


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(
        max_length=30, default=ORDER_STATUS_CHOICES[1][0], choices=ORDER_STATUS_CHOICES
    )
    total_price = models.DecimalField(default=0, max_digits=6, decimal_places=1)
    paid = models.BooleanField(default=False)
    payment_id = models.CharField(
        max_length=250, blank=True, null=True, default="np..."
    )
    is_credit = models.CharField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    total_items = models.SmallIntegerField(default=2)
    carrier = models.ForeignKey(
        "carrier.Carrier", null=True, on_delete=models.SET_NULL, related_name="orders"
    )
    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, related_name="orders"
    )

    class Meta:
        indexes = [models.Index(fields=["-created_at"])]

    def calculate_total_price(self):
        self.total_price = sum(item.subtotal for item in self.items.all())
        self.save()

    def set_total_items(self):
        """returns total items amount in order"""
        self.total_items = sum([item.quantity for item in self.items.all()])
        self.save()

    def get_vendors(self):
        """returns an string containing vendor names spillited by comma"""
        vendors = [
            x["vendor__vendor_name"]
            for x in OrderItem.objects.filter(order=self)
            .values("vendor__vendor_name")
            .distinct()
        ]
        if len(vendors) == 1:
            vendors = vendors[0]
        else:
            vendors = ",".join(vendors)
        return vendors

    def cancel_order(self):
        """reseting food order"""
        print("status", self.status)
        if self.status != ORDER_STATUS_CHOICES[1][0]:  # not waiting
            return
        self.delete()

    def __str__(self):
        return f"Order {self.id} - {self.user.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    food = models.ForeignKey(Food, on_delete=models.CASCADE)
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="order_items"
    )
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(default=0, max_digits=6, decimal_places=1)

    def __str__(self):
        return f"{self.quantity} x {self.food.name} from {self.vendor.vendor_name}"

    @property
    def subtotal(self):
        return self.quantity * self.price

    @property
    def food_name(self):
        return self.food.name
