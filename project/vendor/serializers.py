from rest_framework import serializers
from .models import OpeningHour, Vendor
from accounts.models import REST
from django.utils import timezone
from .utils import to_af_weekday
from zoneinfo import ZoneInfo 


class VendorSerializerMany(serializers.ModelSerializer):
    distance = serializers.SerializerMethodField("get_distance")
    image_url = serializers.SerializerMethodField("get_image_url")

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "avg_rating",
            "rating_count",
            "distance",
            "image_url",
        ]
        

    def get_distance(self, obj):
        # obj.distance is a Distance object; convert to km/miles/etc.
        # distance attribute comes from annotate
        return round(obj.distance.km, 1) if hasattr(obj, "distance") else None

    def get_image_url(self, obj):
        image = getattr(obj.user_profile, "picture", None)
        if image and hasattr(image, "url"):
            return image.url
        return None


class VendorSerializerDetailed(serializers.ModelSerializer):
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:", read_only=True)

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "vendor_license",
            "is_approved",
            "user",
            "user_profile",
            "created_at",
            "avg_rating",
            "rating_count",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_profile",
            "is_approved",
            "created_at",
            "rating",
        ]

    def get_distance(self, obj):
        # obj.distance is a Distance object; convert to km/miles/etc.
        # distance attribute comes from annotate
        return round(obj.distance.km, 1) if hasattr(obj, "distance") else None

    def update(self, instance, validated_data):
        """overriding to apply user profile update together with vendor"""
        # updating user profile if provided
        user_profile_data = validated_data.pop("user_profile", None)
        if user_profile_data:
            existing_user_profile = instance.user_profile
            for attr, value in user_profile_data.items():
                setattr(existing_user_profile, attr, value)
            existing_user_profile.save()

        # updating vendor itself
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance

    def create(self, validated_data):
        user = self.context.get("request").user
        user_profile = user.profile
        user.role = REST
        user.save()
        validated_data["user"] = user
        validated_data["user_profile"] = user_profile

        return super().create(validated_data)


class OpeningHourSerializer(serializers.ModelSerializer):

    class Meta:
        model = OpeningHour
        fields = ["id", "start_hour", "end_hour", "weekday", "is_holiday"]
        read_only_fields = [
            "id",
        ]
