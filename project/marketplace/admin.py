from django.contrib import admin
from .models import Category, Food, Rating

# Register your models here.


class FoodAdmin(admin.ModelAdmin):
    model = Food
    list_display = ["name", "vendor", "is_available", "price"]
    list_editable = ["is_available"]
    list_filter = ["is_available", "vendor"]
    search_fields = ["category__name", "vendor__vendor_name"]


class CategoryAdmin(admin.ModelAdmin):
    model = Category
    list_display = ["name", "created_at"]
    search_fields = ["name"]


class RatingAdmin(admin.ModelAdmin):
    model = Rating
    list_display = ["user", "related_obj", "rating"]


admin.site.register(Rating, RatingAdmin)
admin.site.register(Food, FoodAdmin)
admin.site.register(Category, CategoryAdmin)
