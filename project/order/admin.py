from django.contrib import admin
from .models import FailedMultiVendorPayment, Order, OrderItem
from admins.admin import revenue_admin_site
from django.utils.html import format_html
from django.conf import settings
from .utils import get_hesab_pay_transaction_detail
import json

# Register your models here.
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "vendor", "status", "total_price", "delivery_cost", "paid", "payment_type", "is_epay","location_link", "created_at"]
    list_editable = ["status", "paid"]
    list_filter = ["status", "paid", "payment_type", "is_epay", "created_at", "vendor"]
    search_fields = ["user__name", "user__phone_number", "vendor__vendor_name", "id"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at", "modified_at", "total_price", "delivery_cost", "total_items", "transaction_details"]

    def transaction_details(self, obj):
        """Display HesabPay transaction details for e-pay orders"""
        if not obj.is_epay or not obj.transaction_id:
            return "-"
        
        # Check if required settings are configured
        if not getattr(settings, 'HESAB_PAY_TRANSACTION_DETAILS_ENDPOINT', None) or not getattr(settings, 'HESAB_PAY_API_KEY', None):
            return "HesabPay settings not configured"
        
        try:
            details = get_hesab_pay_transaction_detail(settings.HESAB_PAY_API_KEY, obj.transaction_id)
            if not details:
                return "Unable to fetch transaction details"
            
            # Format the details as HTML for better display
            formatted_details = json.dumps(details, indent=2, ensure_ascii=False)
            return format_html(
                '<pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; max-width: 600px; overflow-x: auto;">{}</pre>',
                formatted_details
            )
        except Exception as e:
            return f"Error fetching transaction details: {str(e)}"
    
    transaction_details.short_description = "HesabPay Transaction Details"

    def location_link(self, obj):
        if not obj.destination:
            return "-"
        return format_html('<a href="https://www.google.com/maps?q={},{}" target="_blank">Map</a>',obj.destination.x,obj.destination.y)

    location_link.allow_tags = True
    location_link.short_description = "Location"

class OrderItemAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "food", "vendor", "quantity", "price", "subtotal"]
    list_filter = ["vendor", "food__category"]
    search_fields = ["order__id", "food__name", "vendor__vendor_name"]
    ordering = ("-id",)
    readonly_fields = ["subtotal"]


class FailedMultiVendorPaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "error_message", "created_at"]
    search_fields = ["order__id", "error_message"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at"]


revenue_admin_site.register(Order, OrderAdmin)
revenue_admin_site.register(OrderItem, OrderItemAdmin)
revenue_admin_site.register(FailedMultiVendorPayment, FailedMultiVendorPaymentAdmin)