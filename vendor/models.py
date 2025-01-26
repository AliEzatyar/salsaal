from django.db import models
from accounts.models import User, UserProfile
from accounts.utils import send_notification

# Create your models here.


class Vendor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vendor")
    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="vendor",
        blank=True,
        null=True,
    )
    vendor_name = models.CharField(max_length=60, unique=True)
    vendor_license = models.ImageField(
        upload_to="vendor/license/", blank=True, null=True
    )
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):

        return self.vendor_name

    def save(self, *args, **kwargs):
        if self.pk != None:
            # update happend
            obj = Vendor.objects.get(pk=self.pk)
            if self.is_approved != obj.is_approved:
                # if there is a changes in approvment of the vendor
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


class Rating(models.Model):
    RATING_CHOICES = ((1, 1), (2, 2), (3, 3), (4, 4), (5, 5))
    vendor = models.ForeignKey(
        "vendor.Vendor", on_delete=models.CASCADE, related_name="vendor_ratings"
    )
    customer = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="+"
    )
    p_quality = models.SmallIntegerField(
        verbose_name="Products Quality", default=0, choices=RATING_CHOICES
    )
    d_time = models.SmallIntegerField(
        verbose_name="Delivery Time", default=0, choices=RATING_CHOICES
    )
    c_service = models.SmallIntegerField(
        verbose_name="Customer Service", default=0, choices=RATING_CHOICES
    )
    created_at = models.DateTimeField(auto_now_add=True, choices=RATING_CHOICES)

    @property
    def overall_rating(self):
        criteria = [self.p_quality, self.d_time, self.c_service]
        return sum(criteria) / len(criteria)

    def save(self, *args, **kwargs):
        """overriding it to avoid duplicate rating"""
        previous = Rating.objects.filter(
            vendor=self.vendor, customer=self.customer
        ).first()
        if previous:
            return previous
        return super().save(*args, **kwargs)
