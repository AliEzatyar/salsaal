from django.contrib import admin
from .models import Category, Food, Rating, Discount

# Register your models here.


class FoodAdmin(admin.ModelAdmin):
    model = Food
    list_display = [
        "id",
        "name",
        "vendor",
        "description",
        "is_available",
        "min_price",
        "category",
        "image",
        "min_price",
    ]
    list_editable = ["is_available","description"]
    list_filter = ["is_available", "vendor","min_price","category"]
    search_fields = ["category__name", "vendor__vendor_name"]


class CategoryAdmin(admin.ModelAdmin):
    model = Category
    list_display = ["name", "created_at"]
    search_fields = ["name"]


class RatingAdmin(admin.ModelAdmin):
    model = Rating
    list_display = ["user", "related_obj", "rating","modified_at"]




class DiscountAdmin(admin.ModelAdmin):
    model = Discount
    list_display = ["id", "vendor", "deadline", "is_active","amount"]


admin.site.register(Discount, DiscountAdmin)

admin.site.register(Rating, RatingAdmin)
admin.site.register(Food, FoodAdmin)
admin.site.register(Category, CategoryAdmin)
