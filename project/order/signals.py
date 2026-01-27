from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from .models import Order, ORDER_STATUS_CHOICES
from django.core.exceptions import ValidationError


@receiver(pre_delete, sender=Order)
def prevent_delivered_order_delete(sender, instance, **kwargs):
    """
    Prevent deletion of delivered orders.
    This signal handler raises a ValidationError if an attempt is made to delete
    an order that has a status indicating it has been delivered. The function is
    triggered by the delete action on an order instance.
    Parameters:
        sender: The model class that sent the signal.
        instance: The actual instance being deleted.
        **kwargs: Additional keyword arguments (not used).
    Raises:
        ValidationError: If the order's status is 'delivered'.
    """
    
    if instance.status == ORDER_STATUS_CHOICES[4][0]: # delivered orders
        raise ValidationError("Delivered orders cannot be deleted")


@receiver(pre_save, sender=Order)
def prevent_delivered_order_status_change(sender, instance, **kwargs):
    """
    Prevent changing the status of an order if it was already delivered.
    """
    if not instance.pk:
        return  # New order, nothing to check
    try:
        previous = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return
    delivered_status = ORDER_STATUS_CHOICES[4][0]
    if previous.status == delivered_status and instance.status != delivered_status:
        raise ValidationError("Cannot change status of a delivered order.")

