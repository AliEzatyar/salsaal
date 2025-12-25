from django.contrib import admin
from .models import Notification
from admins.admin import revenue_admin_site
# Register your models here.


class NotificationAdmin(admin.ModelAdmin):
    list_display = ["id", "receiver", "title", "type", "is_read", "created_at", "target_id"]
    list_editable = ["is_read"]
    list_filter = ["type", "is_read", "created_at"]
    search_fields = ["receiver__name", "receiver__phone_number", "title", "description"]
    ordering = ("-created_at",)
    readonly_fields = ["created_at"]

revenue_admin_site.register(Notification, NotificationAdmin)
