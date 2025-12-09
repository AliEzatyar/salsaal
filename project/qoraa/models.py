from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from marketplace.models import Food
from vendor.models import Vendor
from django.utils.translation import gettext as _
from django.utils.translation import deactivate as deactivate_language
from django.utils.translation import activate as activate_language


MIN_QORAA_PRICE_VALUE = 500  # default price value for any Qoraa
VENDORS_FOR_LOTTERY = "vendors_for_lottery"
PLATFORM_DEFAULT_MORNING_QORAA_TITLE = "Daily Lottery"
PLATFORM_DEFAULT_EVENING_QORAA_TITLE = "Evening Lottery"
QORAA_JOINERS_LIMIT_DEFAULT = 1000000  

class Qoraa(models.Model):
    """
    Lottery model. A Qoraa represents a single lottery window where users may join.

    Fields:
        start: UTC-aware datetime when the lottery starts
        end: UTC-aware datetime when the lottery ends
        status: One of ('scheduled', 'running', 'finished')
        winner: nullable FK to the user who won
        joiners: M2M to users who joined this lottery
        title: optional human-friendly title
        created_at: record creation timestamp
    """

    STATUS_SCHEDULED = "scheduled"
    STATUS_RUNNING = "running"
    STATUS_FINISHED = "finished"

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, "Scheduled"),
        (STATUS_RUNNING, "Running"),
        (STATUS_FINISHED, "Finished"),
    ]

    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_SCHEDULED
    )
    winner = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    food = models.ForeignKey(
        Food, on_delete=models.SET_NULL, related_name="+", blank=True, null=True
    )
    joiners = models.ManyToManyField(
        to=get_user_model(), related_name="qoraas_joined", blank=True
    )
    title = models.CharField(max_length=200, blank=True, default="Daily Lottery")
    created_at = models.DateTimeField(auto_now_add=True)
    price_value = models.PositiveSmallIntegerField(default=MIN_QORAA_PRICE_VALUE)
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="qoraas", null=True, blank=True
    )
    is_platform = models.BooleanField(default=False)
    joiners_limit = models.PositiveIntegerField(
        default=QORAA_JOINERS_LIMIT_DEFAULT,
        help_text="Maximum number of joiners allowed",
    )

    class Meta:
        # ensure we don't accidentally create overlapping identical start times
        ordering = ["-start"]

    def __str__(self) -> str:
        return f"Qoraa {self.title} ({self.start.isoformat()} - {self.end.isoformat()})"

    def is_active(self):
        now = timezone.now()
        return self.start <= now < self.end and self.status == self.STATUS_RUNNING

    def add_joiner(self, user):
        """
        Add a user to joiners if they haven't already joined.

        Returns True if added, False if user already a joiner.
        """
        if self.joiners.filter(pk=user.pk).exists():
            return False
        self.joiners.add(user)
        return True

class PlatformQoraaVendor(models.Model):
    """
    Vendors that are eligible for platform default Qoraa.
    """

    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="platform_qoraa_vendors"
    )
    food_items = models.ManyToManyField(
        Food, related_name="platform_qoraa_vendors", blank=True
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return _(f"PlatformQoraaVendor: {self.vendor.vendor_name}")
