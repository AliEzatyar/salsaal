from django.contrib import admin
from .models import Category, Food, Rating, FavItem, FavList, FoodImage, Discount

# Register your models here.


class FoodAdmin(admin.ModelAdmin):
    model = Food
    list_display = ["name", "vendor", "is_available", "min_price", "default_image"]
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


class FavlistAdmin(admin.ModelAdmin):
    model = FavList
    list_display = ["user"]


class FavlistItemAdmin(admin.ModelAdmin):
    model = FavItem
    list_display = ["favlist", "food"]


class FoodImageAdmin(admin.ModelAdmin):
    model = FoodImage
    list_display = ["id", "image", "food"]


class DiscountAdmin(admin.ModelAdmin):
    model = Discount
    list_display = ["id", "vendor", "deadline", "is_active"]


admin.site.register(FavList, FavlistAdmin)
admin.site.register(FavItem, FavlistItemAdmin)
admin.site.register(FoodImage, FoodImageAdmin)
admin.site.register(Discount, DiscountAdmin)

admin.site.register(Rating, RatingAdmin)
admin.site.register(Food, FoodAdmin)
admin.site.register(Category, CategoryAdmin)
