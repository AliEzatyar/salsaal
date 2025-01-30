from django.contrib import admin
from .models import Rating, Vendor


# Register your models here.
class VendAdmin(admin.ModelAdmin):
    model = Vendor
    list_display = ["vendor_name", "is_approved", "created_at", "modified_at"]
    list_editable = ["is_approved"]


class RatingAdmin(admin.ModelAdmin):
    model = Rating
    list_display = ["customer", "vendor", "overall_rating"]
    

admin.site.register(Vendor, VendAdmin)
admin.site.register(Rating, RatingAdmin)
