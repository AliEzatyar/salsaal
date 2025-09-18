from django.db import models

class Notification(models.Model):
    """
    this class resembles notification db model,
    all sort of users use this model.
    """
    NOTIFICATION_TARGET_TYPES = [
        ("order", "order"),
        ("carrier", "carrier"),
        ("vendor", "vendor"),
        ("reward", "reward"),
        ("other", "other"),
    ]
    receiver = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="notifications"
    )
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20)  # new_order, carriying, delivered, complain,
    data = models.JSONField(blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    target_id = models.IntegerField(null=True, blank=True)
    description = models.CharField(
        max_length=255,null=True, blank=True
    )

    class Meta:
        ordering = ["-created_at"]
