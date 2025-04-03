import os
from django.db.models.signals import post_save
from django.dispatch import receiver

from main.models import FavList
from cart.models import Cart
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
        Cart.objects.get_or_create(user=instance)[0]
        

@receiver(post_save, sender=Vendor)
def delete_cart(sender, instance, created: bool, **kwargs):
    """this signal remove cart from user object when converted to vendor"""
    if created:
        if hasattr(instance,'cart'):
            instance.cart.delete()
            


@receiver(post_save, sender=UserProfile)
def set_default_photos(sender, instance, created, **kwargs):
    """this signal sets default profile photo when new acc. is created"""
    if created:
        prof = instance
        with open(
            os.path.join(settings.BASE_DIR, "static_/images/defaultProfilePicture.jpg"),
            "rb",
        ) as pic:
            prof.cover.save("cover_" + prof.user.username + ".jpg", pic, save=True)
            prof.picture.save("picture_" + prof.user.username + ".jpg", pic, save=True)
