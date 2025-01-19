from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UserProfile,User
from django.contrib.sites.shortcuts import get_current_site

@receiver(post_save,sender=User)
def create_prof(sender, instance, created: bool, **kwargs):
    if created:
        prof = UserProfile(user=instance)
        prof.save()
    else:
        # updated
        pass
    