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
        return int(obj.reach_time) if hasattr(obj, "reach_time") else None

    def get_is_open(self, obj):
        """this checks whether the vendor obj has any opening hour right now"""
        now = timezone.now()  # utc now
        index = now.weekday()  # utc weekday
        weekday = to_af_weekday(index=index)  # afg weekday
        now_af = now.astimezone(ZoneInfo("Asia/Kabul")).hour  # covert to af now
        is_open = False
        today_open_hour = obj.opening_hours.filter(weekday=weekday).first()
        # closed today either always or vendor sets unavailable for some reasons
        if not today_open_hour or not obj.is_available:
            is_open = "closed_today"
        # already closed
        elif today_open_hour.end_hour < now_af:
            is_open = "already_closed"
        # open
        elif today_open_hour.start_hour < now_af and today_open_hour.end_hour > now_af:
            is_open = "yes"
        else:
            is_open = today_open_hour.start_hour
        return is_open


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
            "is_open_now",

        ]

    def get_distance(self, obj):
        # obj.distance is a Distance object; convert to km/miles/etc.
        return obj.distance if hasattr(obj, "distance") else None

    def get_reach_time(self, obj):
        return int(obj.reach_time) if hasattr(obj, "reach_time") else None

    def get_is_open(self, obj):
        """this checks whether the vendor obj has any opening hour right now"""
        now = timezone.now()  # utc now
        index = now.weekday()  # utc weekday
        weekday = to_af_weekday(index=index)  # afg weekday
        now_af = now.astimezone(ZoneInfo("Asia/Kabul")).hour  # covert to af now
        is_open = False
        today_open_hour = obj.opening_hours.filter(weekday=weekday).first()
        # closed today either always or vendor sets unavailable for some reasons
        if not today_open_hour or not obj.is_available:
            is_open = "closed_today"
        # already closed
        elif today_open_hour.end_hour < now_af:
            is_open = "already_closed"
        # open
        elif today_open_hour.start_hour < now_af and today_open_hour.end_hour > now_af:
            is_open = "yes"
        else:
            is_open = today_open_hour.start_hour
        return is_open


class OpeningHourSerializer(serializers.ModelSerializer):

    class Meta:
        model = OpeningHour
        fields = ["id", "start_hour", "end_hour", "weekday", "is_holiday"]
        read_only_fields = ["id"]


class DiscountFoodSerializerMany(serializers.ModelSerializer):
    """used in DiscountSerializer"""

    vendor_name = serializers.SerializerMethodField("get_vendor_name")

    class Meta:
        model = Food
        fields = ["id", "name", "image", "vendor", "vendor_name"]

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
            "mfdd",
            "mfcfd",
            "min_order_price",
            "delivery_fee_km",
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


class PublicVendorSerializer(serializers.ModelSerializer):
    """public vendor details, used in public vendor detail"""

    location = serializers.SerializerMethodField("get_location")  # read only
    # opening_hours = ReadOnlyOpeningHourSerializer(many=True, read_only=True)
    is_open_now = serializers.SerializerMethodField("get_is_open")  # read only

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "location",
            "avg_rating",
            "rating_count",
            "is_open_now",
            "image",
            "logo",
            "mfdd",
            "mfcfd",
            "min_order_price",
            "delivery_fee_km",
        ]
        read_only_fields = ["__all__"]

    def get_location(self, obj):
        """adds vendor location"""
        if obj.get_location():
            return obj.get_location().tuple  # json does not support point object

    def get_is_open(self, obj):
        """this checks whether the vendor obj has any opening hour right now"""
        now = timezone.now()  # utc now
        index = now.weekday()  # utc weekday
        weekday = to_af_weekday(index=index)  # afg weekday
        now_af = now.astimezone(ZoneInfo("Asia/Kabul")).hour  # covert to af now
        is_open = False
        today_open_hour = obj.opening_hours.filter(
            weekday=weekday
        ).first()
        # closed today either always or vendor sets unavailable for some reasons
        if not today_open_hour or not obj.is_available :
            is_open = "closed_today"
        # already closed
        elif today_open_hour.end_hour < now_af:
            is_open = "already_closed"
        # open
        elif today_open_hour.start_hour < now_af and today_open_hour.end_hour > now_af:
            is_open = "yes"
        else:
            is_open = today_open_hour.start_hour 
        return is_open


class AbstractVendorSerializer(serializers.ModelSerializer):
    """
    this serializer has id, location, vendor_name
    used in vendors on map.
    """

    location = serializers.SerializerMethodField("get_location")

    class Meta:
        model = Vendor
        fields = ["id", "location", "vendor_name"]
        read_only_fields = ["__all__"]

    def get_location(self, obj):
        return (obj.user_profile.lattitude, obj.user_profile.longitude)
