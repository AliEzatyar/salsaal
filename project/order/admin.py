from django.contrib import admin
from .models import Order, OrderItem
# Register your models here.
class OrderAdmin(admin.ModelAdmin):
    model = Order
    list_display = ["id","status","user","total_price"]


class OrderItemAdmin(admin.ModelAdmin):
    model = OrderItem
    list_display = ["id","food","price","quantity","order"]

admin.site.register(Order,OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
