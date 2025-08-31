from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey

from accounts.models import UserOtp

# Create your models here.


class Notification(models.Model):
    receiver = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20)  # new_order, carriying, delivered, complain,
    data = models.JSONField(blank=True,null=True)
    is_read = models.BooleanField(default=False)
    date_time = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ["-date_time"]
