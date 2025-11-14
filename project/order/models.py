from django.db import models
from uuid import uuid4
from django.db import models
from django.contrib.auth import get_user_model
from marketplace.models import Food
from vendor.models import Vendor
from django.contrib.gis.db import models as g_models
from django.db.models import Q


User = get_user_model()

ORDER_STATUS_CHOICES = [
    ("cancelled", "cancelled"),
    ("waiting", "waiting"),
    ("preparing", "preparing"),
    ("carrying", "carrying"),
    ("delivered", "delivered"),
]

MAX_PREPARING_ORDERS_COUNT = 1

MAX_ORDER_DELIVERY_TRIES_COUNT = 10

ORDER_DELIVERY_ATTEPMTS_DELAY = 600 

ORDER_DELIVERY_OTP_EXPIRATION = 3 * 60  # 3 hours


VALID_PAYMENT_TYPES = [
    ("cash_on_delivery", "cash_on_delivery"),
    ("hesab_pay", "hesab_pay"),
    ("reward_payment", "reward_payment"),
]


class Order(models.Model):
    """
    Order model representing a customer's order in the system.
    Attributes:
        uuid (UUIDField): Unique identifier for the order.
        user (ForeignKey): Reference to the user who placed the order.
        status (CharField): Current status of the order, with predefined choices.
        total_price (DecimalField): Total price of the order including items and delivery cost.
        delivery_cost (DecimalField): Cost of delivery for the order.
        paid (BooleanField): Indicates whether the order has been paid.
        transaction_id (CharField): Identifier for the payment transaction.
        created_at (DateTimeField): Timestamp when the order was created.
        modified_at (DateTimeField): Timestamp when the order was last modified.
        total_items (SmallIntegerField): Total number of items in the order.
        carrier (ForeignKey): Reference to the carrier handling the order.
        otp (IntegerField): One-time password for order verification.
        vendor (ForeignKey): Reference to the vendor fulfilling the order.
        destination (PointField): Geographical location for delivery.
        payment_type (CharField): Type of payment used for the order.
    Methods:
        calculate_total_price(): Calculates and updates the total price of the order.
        set_total_items(): Updates the total number of items in the order.
        get_vendors(): Returns a string of vendor names associated with the order.
        cancel_order(): Cancels the order if it is in a valid status.
        __str__(): Returns a string representation of the order.
    """

    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.CharField(
        max_length=30, default=ORDER_STATUS_CHOICES[1][0], choices=ORDER_STATUS_CHOICES
    )
    total_price = models.DecimalField(default=0, max_digits=6, decimal_places=1)
    delivery_cost = models.DecimalField(default=0,max_digits=4,decimal_places=1)
    paid = models.BooleanField(default=False)
    transaction_id = models.CharField(
        max_length=250, blank=True, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    total_items = models.SmallIntegerField(default=0)
    carrier = models.ForeignKey(
        "carrier.Carrier", null=True, on_delete=models.SET_NULL, related_name="orders"
    )
    otp = models.IntegerField(null=True, blank=True)
    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, related_name="orders"
    )
    destination = g_models.PointField(null=True, blank=True, srid=4326)
    payment_type = models.CharField(
        max_length=60, choices=VALID_PAYMENT_TYPES, default=VALID_PAYMENT_TYPES[0][0]
    )
    is_epay = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["-created_at"])]
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                check=Q(is_epay=False) | Q(transaction_id__isnull=False),
                name="paid_order_must_have_transaction_id",
            )
        ]

    def calculate_total_price(self):
        self.total_price = sum(item.subtotal for item in self.items.all()) + self.delivery_cost
        return self.total_price

    def set_total_items(self):
        """returns total items amount in order"""
        self.total_items = sum([item.quantity for item in self.items.all()])
        return self.total_items

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
        print("status before cancelling order", self.status)
        if self.status not in [
            ORDER_STATUS_CHOICES[1][1],
            ORDER_STATUS_CHOICES[2][1],
        ]:  # not waiting
            raise Exception("order_not_in_waiting_or_preparing_status")
        self.status = ORDER_STATUS_CHOICES[0][0]
        self.save()

    def __str__(self):
        return f"Order {self.id} - {self.user.name}"


class OrderItem(models.Model):
    """
    OrderItem model represents an item in an order, linking it to a specific order,
    food item, and vendor. It includes details such as quantity and price, and provides
    methods to calculate the subtotal and retrieve the food name.
    Attributes:
        order (ForeignKey): A reference to the Order this item belongs to.
        food (ForeignKey): A reference to the Food item associated with this order item.
        vendor (ForeignKey): A reference to the Vendor providing the food item.
        quantity (PositiveIntegerField): The quantity of the food item ordered.
        price (DecimalField): The price of the food item.
    Methods:
        __str__(): Returns a string representation of the order item, including quantity,
                    food name, and vendor name.
        subtotal: Property that calculates the total price for the quantity of food items.
        food_name: Property that retrieves the name of the food item.
    """
    
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
        return int(self.quantity * self.price)

    @property
    def food_name(self):
        return self.food.name


class Reward(models.Model):
    """
    Reward model represents a reward associated with a user and a vendor.
    Attributes:
        user (ForeignKey): The user who receives the reward.
        vendor (ForeignKey): The vendor associated with the reward.
        amount (FloatField): The amount of the reward, capped at 500.
    Methods:
        save(*args, **kwargs): Overrides the default save method to ensure 
        that the amount does not exceed 500.
    """
    
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="rewards"
    )
    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, related_name="rewards"
    )
    amount = models.FloatField(default=0)

    def save(self, *args, **kwargs):
        if self.amount and self.amount > 500:
            self.amount = 500
        super().save(*args, **kwargs)
