import os
from django.db.models.signals import post_save
from django.dispatch import receiver

from marketplace.models import FavList
from cart.models import Cart
from carrier.models import Carrier
from .models import UserProfile, User
from vendor.models import Vendor
from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings


@receiver(post_save, sender=User)
def create_full_prof(sender, instance, created: bool, **kwargs):
    """this signal creates user profile, cart and favlist"""
    if created: 
        # creating profile
        prof = UserProfile(user=instance)
        prof.save()
        # creating fav list
        fav_list = FavList(user=instance)
        fav_list.save()
        # creating the cart
        
        Cart.objects.get_or_create(user=instance)


@receiver(post_save, sender=Vendor)
def delete_cart_vendor(sender, instance, created: bool, **kwargs):
    """this signal remove cart from user object when converted to vendor"""
    if created:
        if hasattr(instance,'cart'):
            instance.user.cart.delete()


@receiver(post_save, sender=Carrier)
def delete_cart_carrier(sender, instance, created: bool, **kwargs):
    """this signal remove cart from user object when converted to carrier"""
    if created:
        user = instance.user
        if hasattr(user, "cart"):
            user.cart.delete()
