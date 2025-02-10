from django.db import models

# Create your models here.


# Create your models here.
class Cart(models.Model):
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="cart"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    
    def calculate_total_items(self):
        return self.items.count()
    
    def calculate_total(self):
        return sum([item.quantity * item.product.price for item in self.items.all()])

    def __str__(self):
        return f"Cart <{self.user.username}>"


class CartItem(models.Model):
    cart = models.ForeignKey(
        "cart.Cart", on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "marketplace.Product", on_delete=models.CASCADE, related_name="+"
    )
    quantity = models.PositiveSmallIntegerField(default=1)

    def get_total_price(self):
        return self.product.price * self.quantity
