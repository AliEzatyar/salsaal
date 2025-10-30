from decimal import InvalidOperation
import json
from rest_framework import serializers
from vendor.models import OpeningHour, Vendor
from marketplace.models import Category, Food, Rating
from rest_framework import serializers
from decimal import InvalidOperation
import json
from django.db.utils import IntegrityError
from django.db import transaction, IntegrityError
from rest_framework.exceptions import ValidationError

"""custom fields"""


class ListOfDecimalsField(serializers.Field):
    # input
    def to_internal_value(self, data):
        # If it's a string (from form-data), try parsing as JSON
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise serializers.ValidationError("Invalid JSON format.")

        if not isinstance(data, list):
            raise serializers.ValidationError("Prices must be a list.")

        parsed = []
        for value in data:
            try:
                parsed.append(float(str(value)))
            except (ValueError, InvalidOperation):
                raise serializers.ValidationError(
                    f"{value} is not a valid decimal number."
                )
        return parsed

    # output
    def to_representation(self, value):
        return [d for d in value]


class MyDecimalField(serializers.Field):
    def to_representation(self, value):
        return round(float(value), 1)


"""serializers"""


class CategorySerializer(serializers.ModelSerializer):
    """used in home-categories"""

    class Meta:
        model = Category
        fields = ["id", "name", "icon"]


class VFoodSerializerDetail(serializers.ModelSerializer):
    """this serializer is used for vendor-only CRUD"""

    category_name = serializers.ReadOnlyField(source="category.name")
    prices = ListOfDecimalsField()  # custom field to parse form-data prices values
    min_price = MyDecimalField(read_only=True)
    is_available = serializers.BooleanField(default=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)
    discount = serializers.ReadOnlyField(source="discount.amount")
    
    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "min_price",
            "prices",
            "category",
            "description",
            "is_available",
            "image",
            "vendor",
            "duration",
            "ready_time",
            "category_name",
            "is_ready_type",
            "created_at",
            "modified_at",
            "discount"            
        ]
        read_only_fields = [
            "avg_rating",
            "created_at",
            "modified_at",
            "min_price",
            "id",
            "vendor",
            "discount"
        ]

        
    def validate_prices(self,value):
        return value        


    def create(self, validated_data):
        """setting the vendor and min price for the food + preventing duplicates"""
        print(validated_data,"validated data in add food",validated_data)
        validated_data["vendor"] = Vendor.objects.get(id=self.context["vendor"])
        validated_data["min_price"] = min([x for x in validated_data["prices"]])
        name = validated_data.get("name")
        vendor = validated_data.get("vendor")
        # preventing duplicate fooditem
        if self.instance:
            # For update: exclude self
            if (
                Food.objects.filter(vendor=vendor, name__iexact=name)
                .exclude(pk=self.instance.pk)
                .exists()
            ):
                raise serializers.ValidationError(
                    "this_food_name_already_exists_for_this_vendor."
                )
        else:
            # For create
            if Food.objects.filter(vendor=vendor, name__iexact=name).exists():
                raise serializers.ValidationError(
                    "this_food_name_already_exists_for_this_vendor."
                )

        food = Food.objects.create(**validated_data)
        return food

    def update(self, instance, validated_data):
        """
        preventing duplicate foodname.
        """
        try:
            with transaction.atomic():
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                name = validated_data.get("name")
                if name:
                    existing = (
                        Food.objects.filter(name__iexact=name, vendor=instance.vendor)
                        .exclude(pk=self.instance.pk)
                        .exists()
                    )
                    if existing:
                        raise ValidationError({"detail": "foodname_already_used"})
                instance.save()
        except IntegrityError:
            raise ValidationError({"detail": "uknown_problem"})
        return instance

    def to_internal_value(self, data):
        # Convert empty string image to None before validation
        if 'image' in data and data['image'] == '':
            data['image'] = None
        return super().to_internal_value(data)

    def validate(self, attrs):
        """
        overriden to validate if food is ready type or fast food
        if its fast food, it should have duration, else, it should have ready_time which is an hour
        """
        is_ready_type = attrs.get("is_ready_type")
        if is_ready_type:
            if not attrs.get("ready_time"):
                raise serializers.ValidationError(
                    "ready_type_foods_must_have_ready_time"
                )
            attrs["duration"] = None
        else:
            duration = attrs.get("duration")
            if not duration or int(duration) <= 0:
                raise serializers.ValidationError(
                    "fast_food_must_have_cooking_duration"
                )
            attrs["ready_time"] = None

        return super().validate(attrs)


class CVFoodSerializerDetail(serializers.ModelSerializer):
    """used for category"""
    prices = ListOfDecimalsField()  # custom field to parse form-data prices values
    min_price = MyDecimalField(read_only=True)
    vendor_name = serializers.SerializerMethodField("get_vendor_name")
    image = serializers.ReadOnlyField(source="image_url")
    category_name = serializers.ReadOnlyField(source="category.name")

    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "prices",
            "min_price",
            "category_name",
            "description",
            "image",
            "is_available",
            "avg_rating",
            "rating_count",
            "vendor_name",
            "vendor",
            "likes",
        ]
        read_only_fields = ["__all__"]

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name


class FoodSerializerMany(serializers.ModelSerializer):
    """this serializer is used in read only views - customers"""

    vendor_name = serializers.SerializerMethodField("get_vendor_name")
    min_price = MyDecimalField()
    reach_time = serializers.SerializerMethodField("get_reach_time")
    distance = serializers.SerializerMethodField("get_distance")
    image = serializers.ReadOnlyField(source="image_url")
    category_name = serializers.ReadOnlyField(source="category.name")

    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "min_price",
            "prices",
            "image",
            "avg_rating",
            "vendor_name",
            "vendor",
            "rating_count",
            "reach_time",
            "distance",
            "likes",
            "category_name",
        ]

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name

    def get_reach_time(self, obj):
        return int(obj.reach_time) if hasattr(obj, "reach_time") else None

    def get_distance(self, obj):
        return obj.distance if hasattr(obj, "distance") else None


class DiscountedFoodSerializerMany(serializers.ModelSerializer):
    """this serializer is used in read only views - customers home page"""

    reach_time = serializers.SerializerMethodField("get_reach_time")
    distance = serializers.SerializerMethodField("get_distance")
    # original price
    original_price = serializers.SerializerMethodField("get_original_price")
    # discounted price
    vendor_name = serializers.ReadOnlyField(source="vendor.vendor_name")
    discount_amount = serializers.ReadOnlyField(source="discount.amount")
    image = serializers.ReadOnlyField(source="image_url")
    category_name = serializers.ReadOnlyField(source="category.name")

    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "image",
            "original_price", # original price before discount
            "min_price", # current price after discount
            "discount_amount", 
            "vendor",
            "vendor_name",
            "category",
            "reach_time",
            "distance",
            "likes",
            "category_name",
        ]
        read_only_fields = ["__all__"]

    def get_reach_time(self, obj):
        return int(obj.reach_time) if hasattr(obj, "reach_time") else None

    def get_distance(self, obj):
        return obj.distance if hasattr(obj, "distance") else None

    def get_original_price(self, obj):
        """returns original value of min_price"""
        return (obj.min_price / (100 - obj.discount.amount)) * 100


class RatingSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField("get_user_name")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)
    
    class Meta:
        model = Rating
        fields = ["id", "user_name", "comment", "created_at", "rating"]
        read_only_fields = ["id", "created_at", "user"]

    def get_user_name(self, obj):
        return obj.user.full_name


class ReadOnlyOpeningHourSerializer(serializers.ModelSerializer):
    """for marketplace use"""

    class Meta:
        model = OpeningHour
        fields = ["start_hour", "end_hour", "weekday", "is_holiday"]
        read_only_fields = ["id", "start_hour", "end_hour", "weekday", "is_holdiay"]


class FoodSerializerLessDetail(serializers.ModelSerializer):
    min_price = MyDecimalField(read_only=True)
    image = serializers.ReadOnlyField(source="image_url")
    category_name = serializers.ReadOnlyField(source="category.name")
    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "min_price",
            "image",
            "vendor",
            "likes",
            "category_name",
            "description"
        ]


class CategoryVendorSerializer(serializers.ModelSerializer):
    """
    This serializer has vendor_name, distance, reach_time, avg_rating, foods
    The main use is to render foods by category
    used in filter by category.
    {vendor1:{vendor_foods_in_specific_category},...}
    """

    foods = FoodSerializerLessDetail(many=True, read_only=True)
    reach_time = serializers.SerializerMethodField("get_reach_time")
    distance = serializers.SerializerMethodField("get_distance")
    
    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "avg_rating",
            "foods",
            "rating_count",
            "distance",
            "reach_time",
        ]

    def get_distance(self, obj):
        return obj.distance if hasattr(obj, "distance") else None

    def get_reach_time(self, obj):
        return int(obj.reach_time) if hasattr(obj, "reach_time") else None


class CategoryVendorFoodsSerializer(serializers.ModelSerializer):
    """
    This serializer contains `name` and `foods` fields
    it is used to render vendor foods in vendor detail.
    {cat_1:{vendor_foods_in_that_category},cat_2:....}
    """

    foods = FoodSerializerLessDetail(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ["name", "foods"]
