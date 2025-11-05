from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from marketplace.models import Food
from vendor.models import Vendor
from django.utils.translation import gettext as _
from django.utils.translation import deactivate as deactivate_language
from django.utils.translation import activate as activate_language


QORAA_DEFAULT_VALUE = 250  # default price value for any Qoraa
VENDORS_FOR_LOTTERY = "vendors_for_lottery"
PLATFORM_DEFAULT_MORNING_QORAA_TITLE = "Daily Lottery"
PLATFORM_DEFAULT_EVENING_QORAA_TITLE = "Evening Lottery"

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
    foods = models.ManyToManyField(to=Food, related_name="+", blank=True)
    joiners = models.ManyToManyField(
        to=get_user_model(), related_name="qoraas_joined", blank=True
    )
    title = models.CharField(max_length=200, blank=True, default="Daily Lottery")
    created_at = models.DateTimeField(auto_now_add=True)
    price_value = models.PositiveSmallIntegerField(default=QORAA_DEFAULT_VALUE)
    vendor = models.ForeignKey(
        Vendor, on_delete=models.CASCADE, related_name="qoraas", null=True, blank=True
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


class QoraaVendor(models.Model):
    """
    Model to facilitate vendors participate in Qoraa lotteries.
    """

    vendor = models.OneToOneField(
        Vendor, on_delete=models.CASCADE, related_name="qoraa_participation"
    )
    food_items = models.JSONField(default=list)  # list of food item IDs chosen ran
    price_value = models.PositiveSmallIntegerField(
        default=QORAA_DEFAULT_VALUE
    )  # max price value for lottery of this vendor
    title = models.CharField(
        max_length=200, blank=True, default="Daily Lottery"
    )  # custom title for this vendor's lottery
    is_active = models.BooleanField(
        default=True
    )  # whether vendor is actively participating
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(
        upload_to="qoraa_vendor_images/", blank=True, null=True
    )  # optional image for vendor's lottery
    start_date = models.DateField(
        default=timezone.now,
        help_text="Date from which the vendor wants to start participating in lotteries",
    )  # date from which the vendor wants to start participating
    end_date = models.DateField(
        default=timezone.now,
        help_text="Date until which the vendor wants to participate in lotteries (inclusive). Leave blank for indefinite participation.",
    )  # date until which the vendor wants to participate

    class Meta:
        verbose_name = _("Qoraa Vendor")
        verbose_name_plural = _("Qoraa Vendors")

    def __str__(self) -> str:
        return f"QoraaVendor {self.vendor.name} (Active: {self.is_active})"
