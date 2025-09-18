from django.contrib import admin
from .models import Promotion, Vendor, OpeningHour


# Register your models here.
class VendAdmin(admin.ModelAdmin):
    model = Vendor
    list_display = ["vendor_name", "is_approved", "created_at", "modified_at"]
    list_editable = ["is_approved"]


# Register your models here.
class PromotionAdmin(admin.ModelAdmin):
    model = Promotion
    list_display = ["id", "cost_per_day", "city", "is_active", "modified_at"]
    list_editable = ["cost_per_day"]


# Register your models here.
class HourAdmin(admin.ModelAdmin):
    model = OpeningHour
    list_display = ["start_hour", "end_hour", "weekday"]


admin.site.register(OpeningHour,HourAdmin)
admin.site.register(Vendor, VendAdmin)
admin.site.register(Promotion,PromotionAdmin)
