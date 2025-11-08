from django.contrib import admin
from .models import Qoraa, QoraaVendor


@admin.register(Qoraa)
class QoraaAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "vendor",
        "start",
        "end",
        "status",
        "winner",
        "is_platform",
    )
    list_filter = ("status", "is_platform", "start")
    search_fields = ("title", "vendor__name", "winner__username")


@admin.register(QoraaVendor)
class QoraaVendorAdmin(admin.ModelAdmin):
    list_display = ("vendor", "is_active", "is_platform", "start_date", "end_date")
    list_filter = ("is_active", "is_platform")
    search_fields = ("vendor__name",)
