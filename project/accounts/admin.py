from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import User, UserProfile
# Register your models here.

class UserAd(UserAdmin):
    filter_horizontal = ()
    list_display = ['id','username','role','first_name','last_name','email']
    fieldsets = ()
    list_filter = ()
    list_display_links = ['username']


admin.site.register(User,UserAd)
admin.site.register(UserProfile)
