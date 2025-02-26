from django.contrib import admin
from .models import Category, Product, Rating

# Register your models here.


class ProductAdmin(admin.ModelAdmin):
    model = Product
    list_display = ["name", "vendor", "is_available", "inventory", "price", "modified"]
    list_editable = ["is_available"]
    list_filter = ["is_available", "inventory", "vendor"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["category__name", "vendor__vendor_name"]


class CategoryAdmin(admin.ModelAdmin):
    model = Category
    list_display = ["name", "modified", "created_at"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


class RatingAdmin(admin.ModelAdmin):
    model = Rating
    list_display = ["user", "related_obj", "rating"]


admin.site.register(Rating, RatingAdmin)
admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
