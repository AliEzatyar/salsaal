from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User, UserOtp, UserProfile,Device
from order.models import Reward
# Register your models here.

class UserAd(UserAdmin):
    filter_horizontal = ()
    list_display = ['id','role','name','email','phone_number']
    fieldsets = ()
    list_filter = ()
    list_display_links = ['phone_number']
    ordering = ("email",)

class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ["id","user","created_at","token"]

admin.site.register(UserOtp)
admin.site.register(User,UserAd)
admin.site.register(Reward)
admin.site.register(UserProfile)
admin.site.register(Device,UserDeviceAdmin)