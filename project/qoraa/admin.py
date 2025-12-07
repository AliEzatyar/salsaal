from django.contrib import admin
from .models import PlatformQoraaVendor, Qoraa


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


@admin.register(PlatformQoraaVendor)
class PlatformQoraaVendorAdmin(admin.ModelAdmin):
    list_display = ("vendor", "is_active")
    list_filter = ("is_active",)
    search_fields = ("vendor__vendor_name","vendor__id")
