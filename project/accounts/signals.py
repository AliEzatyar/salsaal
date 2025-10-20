from django.db.models.signals import post_save
from django.dispatch import receiver
from cart.models import Cart
from .models import User


@receiver(post_save, sender=User)
def create_full_prof(sender, instance, created: bool, **kwargs):
    """this signal creates user profile, cart and favlist"""
    if created: 
        # creating the cart
        Cart.objects.get_or_create(user=instance)

