from django.contrib import admin
from .models import Vendor

# Register your models here.
class VendAdmin(admin.ModelAdmin):
    model = Vendor
    list_display = ["vendor_name","is_approved","created_at","modified_at"]
    list_editable = ["is_approved"]

admin.site.register(Vendor,VendAdmin)