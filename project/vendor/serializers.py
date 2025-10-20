from zoneinfo import ZoneInfo
from django.contrib.gis.measure  import Distance
from rest_framework import serializers
from django.utils import timezone
from marketplace.models import Discount, Food
from marketplace.serializers import DiscountedFoodSerializerMany, FoodSerializerLessDetail
from vendor.utils import to_af_weekday
from .models import OpeningHour, Promotion, Vendor
from accounts.models import REST
from .models import WEEKDAYS
from rest_framework.serializers import ValidationError


WEEKDAY_MAP = {str(i): val for i, val in WEEKDAYS}


class VendorSerializerMany(serializers.ModelSerializer):
    distance = serializers.SerializerMethodField("get_distance")
    reach_time = serializers.SerializerMethodField("get_reach_time")
    is_open_now = serializers.ReadOnlyField(source="is_available")  # read only

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
            "vendor_type"
        ]

    def get_distance(self, obj):
        # obj.distance is a Distance object; convert to km/miles/etc.
        distance_attr = getattr(obj,"distance",None)
        if type(distance_attr) == Distance:
            return round(obj.distance.km,1)
        return obj.distance if hasattr(obj, "distance") else None

    def get_reach_time(self, obj):
        return int(obj.reach_time) if hasattr(obj, "reach_time") else None

class VendorSerializerWithFoodImages(serializers.ModelSerializer):
    """this provides vendor detail with its foods in `All Venodrs` part"""

    distance = serializers.SerializerMethodField("get_distance")
    reach_time = serializers.SerializerMethodField("get_reach_time")
    foods = FoodSerializerLessDetail(many=True, read_only=True)
    is_open_now = serializers.ReadOnlyField(source="is_available")  # read only

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


class PromotionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Promotion 
        fields = ["image", "vendor","link"]


class VendorSerializerDetailed(serializers.ModelSerializer):
    """used in vendor management views- only vendors access"""

    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:", read_only=True)
    class Meta:
        model = Vendor
        fields = [
            "id",
            "user",
            "user_profile",
            "is_approved",
            "created_at",
            "avg_rating",
            # must fields while converting
            "vendor_name",
            "vendor_license",
            "image",
            "logo",
            "mfdd", # max free delivery distance
            "mfcfd",  # min food count free delivery
            "min_order_price",
            "delivery_fee_km",
            "reward_percentage",
            "vendor_type",
            "latitude",
            "longitude",
            "city"
        ]
        read_only_fields = [
            "id",
            "user",
            "user_profile",
            "is_approved",
            "created_at",
            "avg_rating",
        ]

    def update(self, instance, validated_data):
        """overriding to apply user profile update together with vendor"""
        # custom location validation
        latitude, longitude = validated_data["latitude"], validated_data["longitude"]
        try:
            float(latitude)
            float(longitude)
        except:
            print("lat and lon invalid", latitude, longitude, "--")
            raise ValidationError("provide_correct_lat_lon")
        # updating user profile if provided
        user_profile_data = validated_data.pop("user_profile", None)
        if user_profile_data:
            existing_user_profile = instance.user_profile
            for attr, value in user_profile_data.items():
                setattr(existing_user_profile, attr, value)
            existing_user_profile.save()
        instance.city = str(instance.city).lower()

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
        latitude, longitude = validated_data["latitude"], validated_data["longitude"]
        try:
            float(latitude)
            float(longitude)
            validated_data["city"] = str(validated_data["city"]).lower()
        except:
            print("lat and lon invalid",latitude,longitude,"--")
            raise ValidationError("provide_correct_lat_lon_city")
        validated_data["user"] = user
        validated_data["user_profile"] = user_profile
        return super().create(validated_data)


class PublicVendorSerializer(serializers.ModelSerializer):
    """public vendor details, used in public vendor detail"""
    is_open_now = serializers.ReadOnlyField(source="is_available")  # read only
    discounted_foods = DiscountedFoodSerializerMany(many=True,read_only=True)
    featured_items = serializers.SerializerMethodField(
        "get_featured_items"
    )
    categories = serializers.SerializerMethodField("get_categories")
    reach_time = serializers.SerializerMethodField("get_reach_time")
    categories_count = serializers.IntegerField(read_only=True)
    distance = serializers.SerializerMethodField("get_distance")
    location = serializers.SerializerMethodField("get_location")

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "vendor_type",
            "location",
            "avg_rating",
            "reach_time",
            "rating_count",
            "is_open_now",
            "image",
            "logo",
            "mfdd",
            "mfcfd",
            "min_order_price",
            "discounted_foods",
            "featured_items",
            "categories",
            "categories_count",
            "distance"
        ]
        read_only_fields = ["__all__"]

    def get_categories(self,obj):
        categories = getattr(obj,"categories")
        return categories


    def get_featured_items(self, obj):
        featured = getattr(obj, "featured_items")
        if featured:
            return FoodSerializerLessDetail(featured, many=True).data
        return

    def get_reach_time(self, obj):
        return int(obj.reach_time) if hasattr(obj, "reach_time") else None

    def get_distance(self, obj):
        # obj.distance is a Distance object; convert to km/miles/etc.
        return obj.distance if hasattr(obj, "distance") else None

    def get_location(self, obj):
        if obj.location:
            return [obj.location.y, obj.location.x]
        return


class AbstractVendorSerializer(serializers.ModelSerializer):
    """
    this serializer has id, location, vendor_name
    used in vendors on map.
    """
    location = serializers.SerializerMethodField("get_location")

    class Meta:
        model = Vendor
        fields = ["id", "location", "vendor_name","vendor_type"]
        read_only_fields = ["__all__"]

    def get_location(self,obj):
        if obj.location:
            return [obj.location.y,obj.location.x]
        return 
