from uuid import uuid4
from django.db import models

# Create your models here.


class Cart(models.Model):
    """
    Represents a shopping cart associated with a user.

    Attributes:
        - user: The user who owns the cart.
        - created_at: The timestamp when the cart was created.
        - modified_at: The timestamp when the cart was last modified.
    """
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def calculate_total_items(self):
        """
        Calculate the total number of items in the cart.

        Returns:
            The total quantity of items in the cart.
        """
        if hasattr(self, "items"):
            total = self.items.aggregate(
                total_items=models.Sum("quantity")
            )
            if total["total_items"]:
                return total["total_items"]
        return 0

    def calculate_total(self):
        """
        Calculate the total price of items in the cart.

        Returns:
            The total price of all items in the cart.
        """
        return (
            self.items.aggregate(
                total=models.Sum(models.F("quantity") * models.F("price"))
            )["total"]
            or 0
        )

    def get_vendor(self):
        """
        Retrieve the vendor associated with the first item in the cart.

        Returns:
            The vendor of the first item, or None if the cart is empty.
        """
        return self.items.first().food.vendor if self.items.first() else None

    def clear(self):
        """
        Clear all items from the cart.
        """
        self.items.all().delete()

    def is_empty(self):
        """
        Check if the cart is empty.

        Returns:
            True if the cart is empty, False otherwise.
        """
        return self.items.count() == 0

    def __str__(self):
        return f"Cart <{self.user.name}>"


class CartItem(models.Model):
    """
    Represents an item in a shopping cart.

    Attributes:
        - uuid: A unique identifier for the cart item.
        - cart: The cart to which the item belongs.
        - food: The food item being added to the cart.
        - quantity: The quantity of the food item.
        - price: The price of the food item.
    """
    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )
    cart = models.ForeignKey(
        "cart.Cart", on_delete=models.CASCADE, related_name="items"
    )
    food = models.ForeignKey(
        "marketplace.Food", on_delete=models.CASCADE, related_name="+"
    )
    quantity = models.PositiveSmallIntegerField(default=1)
    price = models.DecimalField(max_digits=6, decimal_places=1)

    @property
    def total_price(self):
        """
        Calculate the total price for this cart item.

        Returns:
            The total price (quantity * price).
        """
        return self.price * self.quantity
