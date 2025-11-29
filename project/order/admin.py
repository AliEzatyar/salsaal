from django.contrib import admin
from .models import FailedMultiVendorPayment, Order, OrderItem


# Register your models here.
class OrderAdmin(admin.ModelAdmin):
    model = Order
    list_display = ["id", "status", "user", "total_price", "is_epay"]
    list_editable = ["status"]


class OrderItemAdmin(admin.ModelAdmin):
    model = OrderItem
    list_display = ["id", "food", "price", "quantity", "order"]


class FailedMultiVendorPaymentAdmin(admin.ModelAdmin):
    model = FailedMultiVendorPayment
    list_display = ["id", "created_at", "order","error_message"]


admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
admin.site.register(FailedMultiVendorPayment, FailedMultiVendorPaymentAdmin)