from django.contrib import admin
from .models import Cart, CartItem

# Register your models here.
class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ["total_price"]

class CartAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "calculate_total_items", "calculate_total", "created_at", "modified_at"]
    search_fields = ["user__name", "user__phone_number"]
    ordering = ("-modified_at",)
    readonly_fields = ["created_at", "modified_at"]
    inlines = [CartItemInline]

class CartItemAdmin(admin.ModelAdmin):
    list_display = ["id", "cart", "food", "quantity", "price", "total_price"]
    list_filter = ["food__category", "food__vendor"]
    search_fields = ["cart__user__name", "cart__user__phone_number", "food__name"]
    ordering = ("-id",)
    readonly_fields = ["total_price"]

admin.site.register(Cart, CartAdmin)
admin.site.register(CartItem, CartItemAdmin)
