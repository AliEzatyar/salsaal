from django.contrib import admin
from .models import Promotion, Vendor
from admins.admin import revenue_admin_site


# Register your models here.
class VendAdmin(admin.ModelAdmin):
    list_display = ["id", "vendor_name", "user", "vendor_type", "is_approved", "is_available", "avg_rating", "city", "created_at"]
    list_editable = ["is_approved", "is_available"]
    list_filter = ["is_approved", "is_available", "vendor_type", "city", "created_at"]
    search_fields = ["vendor_name", "user__name", "user__phone_number", "city"]
    ordering = ("-avg_rating", "-created_at")
    readonly_fields = ["created_at", "modified_at", "avg_rating", "rating_count"]


# Register your models here.
class PromotionAdmin(admin.ModelAdmin):
    list_display = ["id", "vendor", "city", "is_active", "cost_per_day", "start_date", "end_date", "created_at"]
    list_editable = ["is_active", "cost_per_day"]
    list_filter = ["is_active", "city", "start_date", "end_date"]
    search_fields = ["vendor__vendor_name", "city"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at", "modified_at"]


revenue_admin_site.register(Vendor, VendAdmin)
revenue_admin_site.register(Promotion,PromotionAdmin)
