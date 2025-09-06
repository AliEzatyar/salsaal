from zoneinfo import ZoneInfo
from rest_framework.serializers import ModelSerializer, SerializerMethodField
from .models import Notification


class NotificationSerializer(ModelSerializer):
    date_time = SerializerMethodField("get_date_time")

    class Meta:
        model = Notification
        fields = [
            "title",
            "type",
            "data",
            "is_read",
            "date_time",
            "target_id",
            "target_obj_type",
        ]
        read_only_fields = ["__all__"]

    def get_date_time(self, obj):
        return str(obj.date_time.astimezone(ZoneInfo("Asia/Kabul")))
