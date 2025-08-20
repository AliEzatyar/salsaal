from zoneinfo import ZoneInfo
from rest_framework import serializers
from django.utils import timezone
from marketplace.models import Discount, Food
from marketplace.serializers import FoodSerializerLessDetail
from vendor.utils import to_af_weekday
from .models import OpeningHour, Vendor
from accounts.models import REST
from .models import WEEKDAYS
from django.conf import settings

WEEKDAY_MAP = {str(i): val for i, val in WEEKDAYS}


class VendorSerializerMany(serializers.ModelSerializer):
    distance = serializers.SerializerMethodField("get_distance")
    reach_time = serializers.SerializerMethodField("get_reach_time")
    is_open_now = serializers.SerializerMethodField("get_is_open")  # read only
    image = serializers.SerializerMethodField("get_image_url")
    logo = serializers.SerializerMethodField("get_logo_url")

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "avg_rating",
            "rating_count",
            "distance",
            "image",
            "logo",
            "reach_time",
            "is_open_now",
        ]

    def get_distance(self, obj):
        # obj.distance is a Distance object; convert to km/miles/etc.
        return obj.distance if hasattr(obj, "distance") else None

    def get_reach_time(self, obj):
        return obj.reach_time if hasattr(obj, "reach_time") else None

    def get_is_open(self, obj):
        """this checks whether the vendor obj has any opening hour right now"""
        now = timezone.now()  # utc now
        index = now.weekday()  # utc weekday
        weekday = to_af_weekday(index=index)  # afg weekday
        now_af = now.astimezone(ZoneInfo("Asia/Kabul")).hour  # covert to af now
        is_open = obj.opening_hours.filter(
            weekday=weekday, start_hour__lte=now_af, end_hour__gt=now_af
        ).exists()
        return is_open

    def get_image_url(self,obj):
        return settings.CURRENT_DOMAIN_NAME + obj.image.url

    def get_logo_url(self, obj):
        return settings.CURRENT_DOMAIN_NAME + obj.logo.url


class VendorSerializerWithFoodImages(serializers.ModelSerializer):
    """this provides vendor detail with its foods in `All Venodrs` part"""

    distance = serializers.SerializerMethodField("get_distance")
    reach_time = serializers.SerializerMethodField("get_reach_time")
    foods = FoodSerializerLessDetail(many=True, read_only=True)
    is_open_now = serializers.SerializerMethodField("get_is_open")  # read only
    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "avg_rating",
            "rating_count",
            "distance",
            "reach_time",
            "foods",
            "is_open_now"
        ]

    def get_distance(self, obj):
        # obj.distance is a Distance object; convert to km/miles/etc.
        return obj.distance if hasattr(obj, "distance") else None

    def get_reach_time(self, obj):
        return obj.reach_time if hasattr(obj, "reach_time") else None


    def get_is_open(self, obj):
        """this checks whether the vendor obj has any opening hour right now"""
        now = timezone.now()  # utc now
        index = now.weekday()  # utc weekday
        weekday = to_af_weekday(index=index)  # afg weekday
        now_af = now.astimezone(ZoneInfo("Asia/Kabul")).hour  # covert to af now
        is_open = obj.opening_hours.filter(
            weekday=weekday, start_hour__lte=now_af, end_hour__gt=now_af
        ).exists()
        return is_open


class OpeningHourSerializer(serializers.ModelSerializer):

    class Meta:
        model = OpeningHour
        fields = ["id", "start_hour", "end_hour", "weekday", "is_holiday"]
        read_only_fields = ["id"]


class DiscountFoodSerializerMany(serializers.ModelSerializer):
    """used in DiscountSerializer"""

    default_image = serializers.SerializerMethodField("get_photo_url")
    vendor_id = serializers.SerializerMethodField("get_vendor_id")
    vendor_name = serializers.SerializerMethodField("get_vendor_name")

    class Meta:
        model = Food
        fields = ["id", "name", "default_image", "vendor_id", "vendor_name"]

    def get_photo_url(self, obj):
        return settings.CURRENT_DOMAIN_NAME + obj.default_image.image.url

    def get_vendor_id(self, obj):
        return obj.vendor.id

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name


class DiscountSerializer(serializers.ModelSerializer):
    foods = DiscountFoodSerializerMany(read_only=True, many=True)

    class Meta:
        model = Discount
        fields = ["id", "vendor", "amount", "deadline", "foods"]
        read_only_fields = ["id"]


class VendorSerializerDetailed(serializers.ModelSerializer):
    """used in vendor management views- only vendors access"""

    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:", read_only=True)

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "vendor_license",
            "image",
            "logo",
            "is_approved",
            "user",
            "user_profile",
            "created_at",
            "avg_rating",
            "rating_count",
            "opening_hours",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_profile",
            "is_approved",
            "created_at",
            "rating",
            "opening_hours",
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
