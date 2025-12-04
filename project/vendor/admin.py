from django.contrib import admin
from .models import Promotion, Vendor


# Register your models here.
class VendAdmin(admin.ModelAdmin):
    model = Vendor
    list_display = ["id","vendor_name", "is_approved", "created_at", "modified_at"]
    list_editable = ["is_approved"]


# Register your models here.
class PromotionAdmin(admin.ModelAdmin):
    model = Promotion
    list_display = ["id", "cost_per_day", "city", "is_active", "modified_at"]
    list_editable = ["cost_per_day"]



admin.site.register(Vendor, VendAdmin)
admin.site.register(Promotion,PromotionAdmin)
