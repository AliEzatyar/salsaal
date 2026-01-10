from django.contrib import admin, messages
from .models import Category, Food, Rating, Discount
from admins.admin import revenue_admin_site

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
    actions = ["duplicate_food"]

    def duplicate_food(self, request, queryset):
        duplicated_count = 0
        for food in queryset:
            # Create a copy of the food
            new_food = Food(
                vendor=food.vendor,
                name=f"{food.name} (Copy)",
                min_price=food.min_price,
                prices=food.prices,
                category=food.category,
                image=food.image,
                description=food.description,
                is_available=food.is_available,
                discount=food.discount,
                is_featured=food.is_featured,
                likes=0,  # Reset likes for new food
                is_drink=food.is_drink,
                is_ready_type=food.is_ready_type,
                ready_time=food.ready_time,
                duration=food.duration,
            )
            new_food.save()
            duplicated_count += 1
        self.message_user(request, f"Successfully duplicated {duplicated_count} food item(s).", messages.SUCCESS)
    duplicate_food.short_description = "Duplicate selected food(s)"


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


revenue_admin_site.register(Discount, DiscountAdmin)

revenue_admin_site.register(Rating, RatingAdmin)
revenue_admin_site.register(Food, FoodAdmin)
revenue_admin_site.register(Category, CategoryAdmin)
