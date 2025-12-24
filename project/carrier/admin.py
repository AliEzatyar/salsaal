from django.contrib import admin
from .models import Carrier
# Register your models here.

class CarrierAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "user", "vendor", "status", "is_active", "avg_rating"]
    list_editable = ["status", "is_active"]
    list_filter = ["status", "is_active", "vendor"]
    search_fields = ["name", "user__name", "user__phone_number", "vendor__vendor_name"]
    ordering = ("-avg_rating",)
    readonly_fields = ["avg_rating", "rating_count"]

admin.site.register(Carrier, CarrierAdmin)
