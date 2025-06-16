from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey

# Create your models here.


class Notification(models.Model):
    title = models.CharField(max_length=255)
    type = models.CharField(
        max_length=20
    )  # new_order, carriying, delivered, complain,
    data = models.JSONField()
    object_id = models.PositiveIntegerField()
    ct = models.ForeignKey("contenttypes.ContentType", on_delete=models.CASCADE)
    related_object = GenericForeignKey(
        "ct", "object_id"
    )  # this dynammically findes the object
    is_read = models.BooleanField(default=False)
    to  = models.PositiveIntegerField(default=0)