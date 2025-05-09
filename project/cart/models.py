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
                total_items =models.Sum('quantity')
            ) # if no items, none is assigned to total_items
            if total['total_items']:
                return total['total_items']
        return 0

    def calculate_total(self):
        # items = self.items.select_related("food").only("quantity", "food__min_price")
        # return sum(item.quantity * item.food.min_price for item in items)
        return self.items.aggregate(
            total = models.Sum(models.F("quantity") * models.F("food__min_price"))
        )['total'] or 0
        
        
    def __str__(self):
        return f"Cart <{self.user.username}>"


class CartItem(models.Model):
    cart = models.ForeignKey(
        "cart.Cart", on_delete=models.CASCADE, related_name="items"
    )
    food = models.ForeignKey(
        "marketplace.Food", on_delete=models.CASCADE, related_name="+"
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    def get_total_price(self):
        return self.food.min_price * self.quantity
