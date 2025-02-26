from django.db import models
from accounts.models import User, UserProfile
from accounts.utils import send_notification
from marketplace.models import Product
from django.template.loader import render_to_string
# Create your models here.


class Vendor(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="vendor", db_index=True
    )
    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="vendor",
        blank=True,
        null=True,
        db_index=True,
    )

    vendor_name = models.CharField(max_length=60, unique=True, db_index=True)
    vendor_license = models.ImageField(
        upload_to="vendor/license/", blank=True, null=True
    )
    categories = models.ManyToManyField(
        "marketplace.Category", through=Product, db_index=True
    )
    city = models.CharField(default="کابل", db_index=True)
    is_approved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):

        return self.vendor_name

    def create_rating_form(self):
        html = render_to_string(
            "marketplace/rating_form.html", context={"object_id": self.pk}
        )
        return html

    def rating_form(self):
        html = render_to_string(
            "marketplace/rating_form.html",
            context={"object_id": self.pk, "type": "vendor"},
        )
        return html

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
