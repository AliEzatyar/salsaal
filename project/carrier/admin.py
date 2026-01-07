from django.contrib import admin
from .models import Carrier
from admins.admin import revenue_admin_site
# Register your models here.

class CarrierAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "user", "vendor", "status", "is_active", "is_online"]
    list_editable = ["status", "is_active"]
    list_filter = ["status", "is_active", "vendor"]
    search_fields = ["name", "user__name", "user__phone_number", "vendor__vendor_name"]
    ordering = ("-avg_rating",)
    readonly_fields = ["avg_rating", "rating_count"]

revenue_admin_site.register(Carrier, CarrierAdmin)
