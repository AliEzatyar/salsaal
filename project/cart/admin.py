from django.contrib import admin
from .models import Cart, CartItem

# Register your models here.
class CartItemAdmin(admin.ModelAdmin):
    model = CartItem
    list_display = ["food","cart"]

admin.site.register(Cart)
admin.site.register(CartItem,CartItemAdmin)
