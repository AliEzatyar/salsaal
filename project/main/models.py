from django.db import models


# Create your models here.
class FavList(models.Model):
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="favlist"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    def total_items(self):
        return self.items.count()

    def __str__(self):
        return f"FavList <{self.user.username}>"


class FavItem(models.Model):
    favlist = models.ForeignKey(
        "main.FavList", on_delete=models.CASCADE, related_name="items"
    )
    food = models.ForeignKey(
        "marketplace.Food", on_delete=models.CASCADE, related_name="+"
    )
