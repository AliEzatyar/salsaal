from django.db.models.signals import pre_delete
from django.dispatch import receiver
from .models import Order, ORDER_STATUS_CHOICES
from django.core.exceptions import ValidationError


@receiver(pre_delete, sender=Order)
def prevent_delivered_order_delete(sender, instance, **kwargs):
    if instance.status == ORDER_STATUS_CHOICES[4][0]: # delivered orders
        raise ValidationError("Delivered orders cannot be deleted")

