from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import NoUserOtp, User, UserOtp, UserProfile,Device
from order.models import Reward
# Register your models here.

class UserAd(UserAdmin):
    list_display = ["id", "role", "name", "email", "phone_number", "is_active", "is_staff", "created_date"]
    list_filter = ["role", "is_active", "is_staff", "is_superadmin", "region"]
    search_fields = ["name", "email", "phone_number"]
    ordering = ("-created_date",)
    readonly_fields = ["created_date", "modified_date", "last_login", "date_joined"]
    filter_horizontal = ()

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal info', {'fields': ('name', 'email', 'region')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superadmin')}),
        ('Role', {'fields': ('role',)}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'name', 'email', 'password1', 'password2', 'role', 'is_active', 'is_staff', 'is_superadmin'),
        }),
    )

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "pf_lang", "city", "country", "created_at"]
    list_filter = ["pf_lang", "city", "country"]
    search_fields = ["user__name", "user__email", "user__phone_number", "city"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at", "modified_at"]

class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "token", "created_at", "modified_at"]
    search_fields = ["user__name", "user__phone_number", "token"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at", "modified_at"]

class UserOtpAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "otp", "created_at"]
    search_fields = ["user__name", "user__phone_number", "otp"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at"]

class NoUserOtpAdmin(admin.ModelAdmin):
    list_display = ["id", "phone_number", "otp", "created_at"]
    search_fields = ["phone_number", "otp"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at"]

class RewardAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "vendor", "amount"]
    list_filter = ["vendor"]
    search_fields = ["user__name", "user__phone_number", "vendor__vendor_name"]
    ordering = ("-id",)

admin.site.register(UserOtp, UserOtpAdmin)
admin.site.register(NoUserOtp, NoUserOtpAdmin)

admin.site.register(User,UserAd)
admin.site.register(Reward, RewardAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Device,UserDeviceAdmin)
