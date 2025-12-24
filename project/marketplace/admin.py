from django.contrib import admin
from .models import Category, Food, Rating, Discount

# Register your models here.


class FoodAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "vendor",
        "category",
        "min_price",
        "is_available",
        "is_featured",
        "likes",
        "created_at",
    ]
    list_editable = ["is_available", "is_featured"]
    list_filter = ["is_available", "is_featured", "vendor", "category", "is_drink", "is_ready_type", "created_at"]
    search_fields = ["name", "vendor__vendor_name", "category__name"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at", "modified_at", "min_price", "likes"]


class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "show_on_home", "created_at"]
    list_editable = ["show_on_home"]
    search_fields = ["name"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at"]


class RatingAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "related_obj", "rating", "enabled", "created_at", "modified_at"]
    list_filter = ["rating", "enabled", "created_at"]
    search_fields = ["user__name", "user__phone_number"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at", "modified_at"]


class DiscountAdmin(admin.ModelAdmin):
    list_display = ["id", "vendor", "amount", "deadline", "is_active", "created_at"]
    list_editable = ["is_active"]
    list_filter = ["is_active", "vendor", "deadline"]
    search_fields = ["vendor__vendor_name"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at"]


admin.site.register(Discount, DiscountAdmin)

admin.site.register(Rating, RatingAdmin)
admin.site.register(Food, FoodAdmin)
admin.site.register(Category, CategoryAdmin)
