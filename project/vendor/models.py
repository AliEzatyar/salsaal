from uuid import uuid4
from django.db import models
from accounts.models import User, UserProfile
from accounts.utils import send_notification
from marketplace.models import Food, Rating
from django.contrib.contenttypes.models import ContentType

# Create your models here.


class Vendor(models.Model):
    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="vendor",
        db_index=True,
        unique=True,
    )
    user_profile = models.OneToOneField(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="vendor",
        db_index=True,
        unique=True,
    )
    vendor_name = models.CharField(max_length=60, unique=True, db_index=True)
    vendor_license = models.ImageField(upload_to="vendor/license/")
    image = models.ImageField(upload_to="vendor/image/")
    logo = models.ImageField(upload_to="vendor/logo/")
    is_approved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    avg_rating = models.FloatField(default=0)
    rating_count = models.PositiveSmallIntegerField(default=0)
    opening_hours = models.ManyToManyField(
        to="vendor.OpeningHour", related_name="vendors"
    )
    mfdd = models.PositiveSmallIntegerField(
        default=0, blank=True
    )  # max free distance delivery
    mfcfd = models.PositiveSmallIntegerField(
        null=True, blank=True
    )  # min food count free delivery
    min_order_price = models.PositiveSmallIntegerField(default=100)  # AFS
    delivery_fee_km = models.PositiveSmallIntegerField(
        default=3
    )  # delivery fee per km AFS
    is_available = models.BooleanField(default=True)

    class Meta:

        ordering = ["-avg_rating"]

    def get_location(self):
        """returns the location of the vendor"""
        return self.user_profile.location

    def __str__(self):
        return self.vendor_name

    def update_avg_rating(self, *args, **kwargs):
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


HOURS = [(i + add, i + add) for i in range(24) for add in (0,)]
WEEKDAYS = [
    ("1", "Saturday"),
    ("2", "Sunday"),
    ("3", "Monday"),
    ("4", "Tuesday"),
    ("5", "Wednesday"),
    ("6", "Thursday"),
    ("7", "Friday"),
]


class OpeningHour(models.Model):
    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )
    start_hour = models.FloatField(choices=HOURS, null=True)
    end_hour = models.FloatField(choices=HOURS, null=True)
    weekday = models.CharField(choices=WEEKDAYS)
    is_holiday = models.BooleanField(default=False)

    def __str__(self):
        return str(self.start_hour) + "--" + str(self.end_hour)
