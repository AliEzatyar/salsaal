from django.db.models.signals import pre_delete, pre_save, post_save
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
def mark_as_paid(sender, instance, **kwargs):
    """
    Automatically mark an order as paid when its status is updated to 'delivered' by admin.
    This signal handler checks if the order's status has been changed to 'delivered'
    after it has been saved. If so, it updates the order's paid field to True.
    Parameters:
        sender: The model class that sent the signal.
        instance: The actual instance being saved.
        created: A boolean indicating whether a new record was created.
        **kwargs: Additional keyword arguments (not used).
    """
    if  instance.status == ORDER_STATUS_CHOICES[4][0]: # delivered orders
        instance.paid = True

@receiver(pre_save, sender=Order)
def prevent_delivered_order_status_change(sender, instance, **kwargs):
    """
    Prevent changing the status of an order if it was already delivered.
    """
    actor = getattr(instance, '_actor', None)
    if actor and  actor.is_superadmin:
        return  # Superadmins are allowed to change delivered orders
    if not instance.pk:
        return  # New order, nothing to check
    try:
        pre_save_order = Order.objects.get(pk=instance.pk)
    except Order.DoesNotExist:
        return  # Order doesn't exist, nothing to check
    if pre_save_order.status == ORDER_STATUS_CHOICES[4][0]:
        raise ValidationError("Cannot change delivered order.")

