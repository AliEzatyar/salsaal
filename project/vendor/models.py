from django.db import models
from accounts.models import User, UserProfile
from accounts.utils import send_notification
from marketplace.models import Food, Rating
from django.contrib.contenttypes.models import ContentType

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
    avg_rating = models.FloatField(default=0)
    rating_count = models.PositiveSmallIntegerField(default=0)
    
    class Meta:
        
        ordering = ['-avg_rating']
    
    def get_location(self):
        """returns the location of the vendor"""
        return self.user_profile.location

    def __str__(self):
        return self.vendor_name

    def update_avg_rating(self,*args, **kwargs):
        ct = ContentType.objects.get_for_model(Vendor)
        avg_and_count = Rating.objects.filter(
            object_id=self.pk,
            content_type=ct,
        ).aggregate(avg=models.Avg("rating"), count=models.Count("rating"))
        self.avg_rating = avg_and_count["avg"] or 0.0
        self.rating_count = avg_and_count["count"] or 0
        self.save()

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
