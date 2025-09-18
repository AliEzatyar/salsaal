from django.contrib import admin
from .models import Notification
# Register your models here.


class NotificationAdmin(admin.ModelAdmin):
    model = Notification
    list_display = ["id", "receiver", "created_at", "target_id"]


admin.site.register(Notification,NotificationAdmin)
