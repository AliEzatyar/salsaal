from django.db import models

CARRIER_STATUS_CHOICES = [
    ("free", "free"),
    ("busy", "busy"),
]

# Create your models here.
class Carrier(models.Model):
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
    is_active  = models.BooleanField(default=False)
    
    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        """making name automated"""
        self.name = self.user.first_name + " " + self.user.last_name
        return super().save(*args, **kwargs)
