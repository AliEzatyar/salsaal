from zoneinfo import ZoneInfo
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from .models import Notification


class NotificationSerializer(ModelSerializer):
    created_at = SerializerMethodField("get_created_at")

    class Meta:
        model = Notification
        fields = [
            "title",
            "type",
            "data",
            "is_read",
            "created_at",
            "target_id",
            "description",
        ]
        read_only_fields = ["__all__"]

    def get_created_at(self, obj):
        return str(obj.created_at.astimezone(ZoneInfo("Asia/Kabul")))
