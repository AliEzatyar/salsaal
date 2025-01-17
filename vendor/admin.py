from django.contrib import admin
from .models import Vendor

# Register your models here.
class VendAdmin(admin.ModelAdmin):
    model = Vendor
    list_display = ["vendor_name","is_approved","created_at","modified_at"]


admin.site.register(Vendor,VendAdmin)