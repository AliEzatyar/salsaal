from django.contrib import admin
from .models import FailedMultiVendorPayment, Order, OrderItem
from admins.admin import revenue_admin_site


# Register your models here.
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "vendor", "status", "total_price", "delivery_cost", "paid", "payment_type", "is_epay", "created_at"]
    list_editable = ["status", "paid"]
    list_filter = ["status", "paid", "payment_type", "is_epay", "created_at", "vendor"]
    search_fields = ["user__name", "user__phone_number", "vendor__vendor_name", "id"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at", "modified_at", "total_price", "delivery_cost", "total_items"]


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