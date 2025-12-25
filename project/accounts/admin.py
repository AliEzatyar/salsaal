from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html

from accounts.models import NoUserOtp, User, UserOtp, UserProfile,Device
from order.models import Reward
from admins.admin import revenue_admin_site
# Register your models here.

class UserAd(UserAdmin):
    list_display = ["id", "role", "name", "email", "phone_number", "is_active", "is_staff", "get_groups", "created_date"]
    list_filter = ["role", "is_active", "is_staff", "is_superadmin", "region", "groups"]
    search_fields = ["name", "email", "phone_number"]
    ordering = ("-created_date",)
    readonly_fields = ["created_date", "modified_date", "last_login", "date_joined"]
    filter_horizontal = ('groups', 'user_permissions')
    actions = ['assign_to_group_action', 'remove_from_group', 'bulk_assign_by_role']

    fieldsets = (
        (None, {'fields': ('phone_number', 'password')}),
        ('Personal info', {'fields': ('name', 'email', 'region')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superadmin', 'groups', 'user_permissions')}),
        ('Role', {'fields': ('role',)}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('phone_number', 'name', 'email', 'password1', 'password2', 'role', 'is_active', 'is_staff', 'is_superadmin'),
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('assign-group/', self.admin_site.admin_view(self.assign_group_view), name='assign_group'),
        ]
        return custom_urls + urls

    def assign_group_view(self, request):
        if request.method == 'POST':
            group_id = request.POST.get('group')
            user_ids = request.POST.getlist('users')

            if group_id and user_ids:
                try:
                    group = Group.objects.get(id=group_id)
                    users = User.objects.filter(id__in=user_ids)
                    count = 0
                    for user in users:
                        if not user.groups.filter(id=group_id).exists():
                            user.groups.add(group)
                            count += 1

                    messages.success(request, f"Added {count} users to group '{group.name}'.")
                    return redirect('..')
                except Group.DoesNotExist:
                    messages.error(request, "Group not found.")

        groups = Group.objects.all()
        selected_users = request.GET.getlist('ids')
        users = User.objects.filter(id__in=selected_users) if selected_users else []

        context = {
            'groups': groups,
            'users': users,
            'title': 'Assign Users to Group',
            'opts': self.model._meta,
        }
        return render(request, 'admin/accounts/user/assign_group.html', context)

    def get_groups(self, obj):
        groups = obj.groups.all()
        if groups:
            return format_html(", ".join([f'<span style="background-color: #f0f0f0; padding: 2px 4px; border-radius: 3px; font-size: 11px;">{group.name}</span>' for group in groups]))
        return "No groups"
    get_groups.short_description = 'Groups'

    def assign_to_group_action(self, request, queryset):
        selected = request.POST.getlist(admin.ACTION_CHECKBOX_NAME)
        return redirect(f'assign-group/?ids={",".join(selected)}')
    assign_to_group_action.short_description = "Assign selected users to a group"

    def remove_from_group(self, request, queryset):
        # For simplicity, remove from all groups. In a real implementation,
        # you might want to show a form to select which group
        count = 0
        for user in queryset:
            user.groups.clear()
            count += 1

        self.message_user(request, f"Removed {count} users from all groups.", messages.SUCCESS)
    remove_from_group.short_description = "Remove selected users from all groups"

    def bulk_assign_by_role(self, request, queryset):
        # Define role to group mappings
        role_group_mapping = {
            0: 'Site Admin',      # ADMIN
            1: 'Vendor Manager',  # REST (Restaurant)
            2: 'Support Staff',   # CUSTOMER
            3: 'Order Manager',   # CARRIER
        }

        assigned_count = 0
        for user in queryset:
            group_name = role_group_mapping.get(user.role)
            if group_name:
                try:
                    group = Group.objects.get(name=group_name)
                    if not user.groups.filter(name=group_name).exists():
                        user.groups.add(group)
                        assigned_count += 1
                except Group.DoesNotExist:
                    continue

        self.message_user(request, f"Assigned {assigned_count} users to groups based on their roles.", messages.SUCCESS)
    bulk_assign_by_role.short_description = "Assign users to groups based on their role"

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

revenue_admin_site.register(UserOtp, UserOtpAdmin)
revenue_admin_site.register(NoUserOtp, NoUserOtpAdmin)

revenue_admin_site.register(User,UserAd)
revenue_admin_site.register(Reward, RewardAdmin)
revenue_admin_site.register(UserProfile, UserProfileAdmin)
revenue_admin_site.register(Device,UserDeviceAdmin)


# Custom Group Admin for better group management
class GroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_user_count', 'get_permissions_count']
    search_fields = ['name']
    ordering = ['name']

    def get_user_count(self, obj):
        return obj.custom_user_set.count()
    get_user_count.short_description = 'Users'

    def get_permissions_count(self, obj):
        return obj.permissions.count()
    get_permissions_count.short_description = 'Permissions'

    def get_form(self, request, obj=None, **kwargs):
        # Customize the form to make permissions more manageable
        form = super().get_form(request, obj, **kwargs)
        if 'permissions' in form.base_fields:
            form.base_fields['permissions'].widget.attrs['style'] = 'height: 300px;'
        return form

# Register the custom Group admin with the custom admin site
revenue_admin_site.register(Group, GroupAdmin)
