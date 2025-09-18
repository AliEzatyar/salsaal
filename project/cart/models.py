from uuid import uuid4
from django.db import models

# Create your models here.


# Create your models here.
class Cart(models.Model):
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def calculate_total_items(self):
        if hasattr(self, "items"):
            total = self.items.aggregate(
                total_items=models.Sum("quantity")
            )  # if no items, none is assigned to total_items
            if total["total_items"]:
                return total["total_items"]
        return 0

    def calculate_total(self):
        # items = self.items.select_related("food").only("quantity", "food__min_price")
        # return sum(item.quantity * item.food.min_price for item in items)
        return (
            self.items.aggregate(
                total=models.Sum(models.F("quantity") * models.F("price"))
            )["total"]
            or 0
        )

    def get_vendor(self):
        return self.items.first().food.vendor if self.items.first() else None

    def clear(self):
        self.items.all().delete()


    def is_empty(self):
        count = self.items.count()
        if count > 0:
            return False
        return True

    def __str__(self):
        return f"Cart <{self.user.full_name}>"

class CartItem(models.Model):
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

    def get_total_price(self):
        return self.price * self.quantity
