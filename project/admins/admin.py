from django.contrib import admin
from django_otp.plugins.otp_totp.models import TOTPDevice


@admin.register(TOTPDevice)
class TOTPDeviceAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "confirmed", "last_used")
    list_filter = ("confirmed",)
    search_fields = ("user__username", "name")

    # Optional: define a method if you want to show last TOTP usage
    def last_used(self, obj):
        # This returns the last login time via this device if available
        return getattr(obj, "last_t", None)  # adjust according to your model

    last_used.short_description = "Last TOTP"
