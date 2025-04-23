from django.db import models
from accounts.models import User, UserProfile
from accounts.utils import send_notification
from marketplace.models import Food, Rating
from django.template.loader import render_to_string

# Create your models here.


class Vendor(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="vendor", db_index=True,unique=True
    )
    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="vendor",
        db_index=True,
        unique=True
    )
    vendor_name = models.CharField(max_length=60, unique=True, db_index=True)
    vendor_license = models.ImageField(
        upload_to="vendor/license/"
    )
    is_approved = models.BooleanField(default=False, db_index=True)
    active_hours = models.CharField(max_length=255,default="11:00-2:00 PM,5:00-9:00 PM")  # comma seperated
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def get_location(self):
        """returns the location of the vendor"""
        return self.user_profile.location

    def __str__(self):
        return self.vendor_name

    def rating_form(self):
        """automates rating form template"""
        html = render_to_string(
            "marketplace/rating_form.html",
            context={"object_id": self.pk, "type": "vendor"},
        )
        return html

    def overall_rating(self):
        """this utility method returns the rating average"""
        ratings = Rating.objects.filter(object_id=self.pk).values_list("rating")
        ratings = [r[0] for r in ratings]
        if len(ratings) == 0:
            return 0
        return sum(ratings) / len(ratings)

    def save(self, *args, **kwargs):
        """overriding to send approved email"""
        if self.pk != None:
            # update happend
            obj = Vendor.objects.get(pk=self.pk)
            if self.is_approved != obj.is_approved:
                # if there is changes in approvment of the vendor
                context = {"user": self.user, "is_approved": self.is_approved}
                template = "accounts/emails/admin_approval_email.html"
                if self.is_approved:
                    # approved notification email sending
                    title = "Congratulations! Your Shop Has Been Approved By Salsaal E-Commerce."
                    send_notification(self.user.email, title, template, context)
                else:
                    # approved notification email sending
                    title = "We Are Sorry, Your Shop Is Not Approved!"
                    send_notification(self.user.email, title, template, context)
        return super(Vendor, self).save(*args, **kwargs)
