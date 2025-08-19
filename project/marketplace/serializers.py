from decimal import InvalidOperation
import json
from zoneinfo import ZoneInfo
from rest_framework import serializers
from vendor.utils import to_af_weekday
from vendor.models import OpeningHour, Vendor
from marketplace.models import Category, FavItem, FavList, Food, FoodImage, Rating
from rest_framework import serializers
from decimal import InvalidOperation
import json
from django.db.utils import IntegrityError
from django.utils import timezone
from django.conf import settings
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
        return round(float(value), 2)


"""serializers"""


class CategorySerializer(serializers.ModelSerializer):
    """used in home-categories"""

    class Meta:
        model = Category
        fields = ["id", "name", "picture"]


class FoodImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = FoodImage
        fields = ["food", "image"]


class FoodSerializerDetail(serializers.ModelSerializer):
    """this serializer is used for vendor-only CRUD"""

    category_name = serializers.SerializerMethodField("get_category_name")
    prices = ListOfDecimalsField()  # custom field to parse form-data prices values
    min_price = MyDecimalField(read_only=True)
    is_available = serializers.BooleanField(default=True)
    images = FoodImageSerializer(many=True, read_only=True)
    uploaded_images = serializers.ListField(
        child=serializers.ImageField(), write_only=True, required=True
    )
    default_image = serializers.SerializerMethodField("get_image_url")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)
    vendor_id = serializers.SerializerMethodField("get_vendor_id")

    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "min_price",
            "prices",
            "category",
            "category_name",
            "description",
            "is_available",
            "images",
            "default_image",
            "uploaded_images",
            "avg_rating",
            "rating_count",
            "created_at",
            "modified_at",
            "vendor_id",
        ]
        read_only_fields = [
            "avg_rating",
            "created_at",
            "modified_at",
            "min_price",
            "id",
            "images",
            "default_image",
        ]

    def get_image_url(self, obj):
        if hasattr(obj.default_image, "image"):
            return settings.CURRENT_DOMAIN_NAME + obj.default_image.image.url

    def get_category_name(self, obj):
        return obj.category.name

    def create(self, validated_data):
        """setting the vendor and min price for the food + preventing duplicates+ handling multiple images"""
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
                    "This food name already exists for this vendor."
                )
        else:
            # For create
            if Food.objects.filter(vendor=vendor, name__iexact=name).exists():
                raise serializers.ValidationError(
                    "This food name already exists for this vendor."
                )

        # handling multiple images
        images = validated_data.pop("uploaded_images", [])
        food = Food.objects.create(**validated_data)
        for i, image in enumerate(images):
            img_obj = FoodImage.objects.create(image=image, food=food)
            # selecting first image as default
            if i == 0:
                food.default_image = img_obj

        food.save()
        return food

    def update(self, instance, validated_data):
        """
        preventing duplicate foodname and updating images if provided any.
        """
        images = validated_data.pop("uploaded_images", [])
        try:
            with transaction.atomic():
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                name = validated_data.get("name")
                if name:
                    existing = (
                        Food.objects.filter(name=name, vendor=instance.vendor)
                        .exclude(pk=self.instance.pk)
                        .exists()
                    )
                    if existing:
                        raise ValidationError({"detail": "foodname_already_used"})
                # deleting all previous images
                if len(images) > 0:
                    for image in instance.images.all():
                        image.delete()
                # creating images
                for i, image in enumerate(images):
                    img_obj = FoodImage.objects.create(image=image, food=instance)
                    # selecting first image as default
                    if i == 0:
                        instance.default_image = img_obj
                instance.save()
        except IntegrityError:
            raise ValidationError({"detail": "uknown_problem"})
        return instance

    def get_vendor_id(self, obj):
        return obj.vendor.id


class CFoodSerializerDetail(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField("get_category_name")
    prices = ListOfDecimalsField()  # custom field to parse form-data prices values
    min_price = MyDecimalField(read_only=True)
    images = FoodImageSerializer(many=True, read_only=True)
    default_image = serializers.SerializerMethodField("get_image_url")
    vendor_name = serializers.SerializerMethodField("get_vendor_name")
    vendor_id = serializers.SerializerMethodField("get_vendor_id")

    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "prices",
            "min_price",
            "category_name",
            "description",
            "images",
            "default_image",
            "is_available",
            "avg_rating",
            "rating_count",
            "vendor_name",
            "vendor_id",
        ]
        read_only_fields = ["__all__"]

    def get_category_name(self, obj):
        return obj.category.name

    def get_image_url(self, obj):
        return settings.CURRENT_DOMAIN_NAME + obj.default_image.image.url

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name

    def get_vendor_id(self, obj):
        return obj.vendor.id


class FoodSerializerMany(serializers.ModelSerializer):
    """this serializer is used in read only views - customers"""

    vendor_name = serializers.SerializerMethodField("get_vendor_name")
    vendor_id = serializers.SerializerMethodField("get_vendor_id")

    min_price = MyDecimalField()
    default_image = serializers.SerializerMethodField("get_photo_url")
    reach_time = serializers.SerializerMethodField("get_reach_time")
    distance = serializers.SerializerMethodField("get_distance")

    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "min_price",
            "prices",
            "default_image",
            "avg_rating",
            "vendor_name",
            "vendor_id",
            "rating_count",
            "reach_time",
            "distance",
        ]

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name

    def get_vendor_id(self, obj):
        return obj.vendor.id

    def get_photo_url(self, obj):
        return settings.CURRENT_DOMAIN_NAME + obj.default_image.image.url

    def get_reach_time(self, obj):
        return obj.reach_time if hasattr(obj, "reach_time") else None

    def get_distance(self, obj):
        return obj.distance if hasattr(obj, "distance") else None


class DiscountedFoodSerializerMany(serializers.ModelSerializer):
    """this serializer is used in read only views - customers home page"""

    default_image = serializers.SerializerMethodField("get_photo_url")
    final_price = serializers.SerializerMethodField("get_final_price")
    min_price = MyDecimalField()
    vendor_id = serializers.SerializerMethodField("get_vendor_id")
    vendor_name = serializers.SerializerMethodField("get_vendor_name")

    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "default_image",
            "discount",
            "final_price",
            "vendor_id",
            "vendor_name",
            "min_price",
            "category",
        ]

    def get_photo_url(self, obj):
        return settings.CURRENT_DOMAIN_NAME + obj.default_image.image.url

    def get_final_price(self, obj):
        return (
            obj.min_price * (100 - obj.discount.amount) / 100
            if hasattr(obj, "discount")
            else None
        )


    def get_vendor_id(self, obj):
        return obj.vendor.id

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name



class RatingSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField("get_user_name")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "user", "user_name", "comment", "created_at", "rating"]
        read_only_fields = ["id", "created_at", "user"]

    def get_user_name(self, obj):
        return obj.user.get_full_name()


class ReadOnlyOpeningHourSerializer(serializers.ModelSerializer):
    """for marketplace use"""

    class Meta:
        model = OpeningHour
        fields = ["start_hour", "end_hour", "weekday", "is_holiday"]
        read_only_fields = ["id", "start_hour", "end_hour", "weekday", "is_holdiay"]


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
            # "opening_hours",
            "is_open_now",
            "image",
            "logo"
        ]
        read_only_fields = ["id", "is_open_now"]

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
        is_open = obj.opening_hours.filter(
            weekday=weekday, start_hour__lte=now_af, end_hour__gt=now_af
        ).exists()
        return is_open



class FavItemSerializer(serializers.ModelSerializer):
    food_name = serializers.SerializerMethodField("get_food_name", read_only=True)
    picture = serializers.SerializerMethodField("get_food_picture", read_only=True)

    class Meta:
        model = FavItem
        fields = ["id", "food", "food_name", "picture"]
        read_only_fields = ["picture", "food_name"]

    def create(self, validated_data):
        favlist = FavList.objects.filter(id=self.context["favlist"]).first()
        exists = favlist.items.filter(food=validated_data["food"]).exists()
        if exists:
            raise serializers.ValidationError(detail="already_exists")
        if not favlist:
            raise serializers.ValidationError(detail="no_fav_list")
        validated_data["favlist"] = favlist
        return super().create(validated_data)

    def get_food_name(self, obj):
        return obj.food.name

    def get_food_picture(self, obj):
        return obj.food.default_image.image.url


class FavListSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField("get_user_name", read_only=True)

    class Meta:
        model = FavList
        fields = ["user", "user_name"]
        read_only_fields = ["user_name"]

    def get_user_name(self, obj):
        return obj.user.get_full_name()


class FoodSerializerLessDetail(serializers.ModelSerializer):
    vendor_id = serializers.SerializerMethodField("get_vendor_id")
    image = serializers.SerializerMethodField("get_image_url")

    class Meta:
        model = Food
        fields = [
            "name",
            "min_price",
            "image",
            "rating_count",
            "avg_rating",
            "vendor_id",
        ]

    def get_vendor_id(self, obj):
        return obj.vendor.id

    def get_image_url(self, obj):
        return settings.CURRENT_DOMAIN_NAME + obj.default_image.image.url


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
        fields = ["vendor_name", "distance", "reach_time", "avg_rating", "foods"]

    def get_distance(self, obj):
        return obj.distance if hasattr(obj, "distance") else None

    def get_reach_time(self, obj):
        return obj.reach_time if hasattr(obj, "reach_time") else None


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


class AbstractVendorSerializer(serializers.ModelSerializer):
    """
    this serializer has id, location, vendor_name
    used in vendors on map.
    """

    location = serializers.SerializerMethodField("get_location")

    class Meta:
        model = Vendor
        fields = ["id", "location", "vendor_name"]

    def get_location(self, obj):
        return (obj.user_profile.lattitude, obj.user_profile.longitude)
