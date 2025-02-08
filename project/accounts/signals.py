import os
from django.db.models.signals import post_save
from django.dispatch import receiver

from main.models import FavList
from .models import UserProfile, User
from django.contrib.sites.shortcuts import get_current_site
from django.conf import settings


@receiver(post_save, sender=User)
def create_prof(sender, instance, created: bool, **kwargs):
    if created:
        prof = UserProfile(user=instance)
        prof.save()


@receiver(post_save, sender=User)
def create_prof(sender, instance, created: bool, **kwargs):
    if created:
        fav_list = FavList(user=instance)
        fav_list.save()


@receiver(post_save, sender=UserProfile)
def set_default_photos(sender, instance, created, **kwargs):
    if created:
        prof = instance
        with open(
            os.path.join(settings.BASE_DIR, "static_/images/defaultProfilePicture.jpg"),
            "rb",
        ) as pic:
            prof.cover.save("cover_" + prof.user.username + ".jpg", pic, save=True)
            prof.picture.save("picture_" + prof.user.username + ".jpg", pic, save=True)
