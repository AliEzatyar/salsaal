from django.db import models
from uuid import uuid4

# Create your models here.
from django.db import models
from django.contrib.auth import get_user_model
from marketplace.models import Food
from accounts.utils import generate_otp
from vendor.models import Vendor

User = get_user_model()

ORDER_STATUS_CHOICES = [
    ("cancelled", "cancelled"),
    ("waiting", "waiting"),
    ("preparing", "preparing"),
    ("carrying", "carrying"),
    ("delivered", "delivered"),
]

VALID_PAYMENT_TYPES = [
    ("cash_on_delivery", "cash_on_delivery"),
    ("hesab_pay", "hesab_pay"),
    ("debit_card", "debit_card"),
]


class Order(models.Model):
    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )
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
    otp = models.IntegerField(null=True, blank=True)
    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, related_name="orders"
    )
    destination = models.CharField(max_length=40, default="null,null")
    payment_type = models.CharField(
        max_length=60, choices=VALID_PAYMENT_TYPES, default=VALID_PAYMENT_TYPES[0][0]
    )

    class Meta:
        indexes = [models.Index(fields=["-created_at"])]
        ordering = ["-created_at"]

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
        if self.status not in [
            ORDER_STATUS_CHOICES[1][1],
            ORDER_STATUS_CHOICES[2][1],
        ]:  # not waiting
            raise Exception("order_not_in_waiting_or_preparing_status")
        self.status = ORDER_STATUS_CHOICES[0][0]
        self.save()

    def save(self, *args, **kwargs):
        """this method is overriden for auto-filling otp of order"""
        if not self.pk:
            otp = generate_otp(8)
            self.otp = otp

        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.id} - {self.user.full_name}"


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
