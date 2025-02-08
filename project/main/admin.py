from django.contrib import admin

from main.models import FavItem, FavList

# Register your models here.

class FavlistAdmin(admin.ModelAdmin):
    model =  FavList
    list_display = ["user","created_at"]


class FavlistItemAdmin(admin.ModelAdmin):
    model = FavItem
    list_display = ["favlist","product"]


admin.site.register(FavList, FavlistAdmin)
admin.site.register(FavItem,FavlistItemAdmin)
