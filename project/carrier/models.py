from uuid import uuid4
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.db.models import Avg, Count
from marketplace.models import Rating

CARRIER_STATUS_CHOICES = [
    ("free", "free"),
    ("busy", "busy"),
]

# Create your models here.
class Carrier(models.Model):
    uuid = models.UUIDField(
        default=uuid4, db_index=True, unique=True, editable=False, null=True
    )
    user = models.OneToOneField(
        "accounts.User", on_delete=models.CASCADE, related_name="carrier"
    )
    user_profile = models.OneToOneField(
        "accounts.UserProfile", on_delete=models.CASCADE, related_name="+"
    )
    name = models.CharField(max_length=60, default="NoName")
    id_document = models.ImageField(upload_to="carrier/ids/", null=True, blank=True)
    vendor = models.ForeignKey('vendor.Vendor',on_delete=models.CASCADE,related_name="carriers")
    status = models.CharField(choices=CARRIER_STATUS_CHOICES,default=CARRIER_STATUS_CHOICES[0][0])
    is_active  = models.BooleanField(default=True)
    avg_rating = models.FloatField(default=0)
    rating_count = models.PositiveSmallIntegerField(default=0)
    is_online = models.BooleanField(default=True)
    
    class Meta:
        ordering = ["name"]

    def update_avg_rating(self, *args, **kwargs):
        ct = ContentType.objects.get_for_model(Carrier)
        avg_and_count = Rating.objects.filter(
            object_id=self.pk,
            content_type=ct,
        ).aggregate(avg=models.Avg("rating"), count=models.Count("rating"))
        self.avg_rating = avg_and_count["avg"] or 0.0
        self.rating_count = avg_and_count["count"] or 0
        self.save()

    def save(self,*args, **kwargs):
        if not self.pk:
            self.name = self.user.name
        return super().save(*args, **kwargs)
