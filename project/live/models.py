from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey

# Create your models here.


class Notification(models.Model):
    
    receiver = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE,null=True, related_name="sent_notifications"
    )
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20)  # new_order, carriying, delivered, complain,
    data = models.JSONField(blank=True,null=True)
    target = models.PositiveIntegerField(null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
