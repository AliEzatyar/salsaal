from decimal import Decimal, InvalidOperation
import json
from rest_framework import serializers
from vendor.models import Vendor
from marketplace.models import Category, FavItem, FavList, Food, FoodImage, Rating
from rest_framework import serializers
from decimal import Decimal, InvalidOperation
import json
from django.contrib.gis.db.models.fields import PointField

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

    class Meta:
        model = Category
        fields = ["name"]


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
        child=serializers.ImageField(), write_only=True, required=False
    )
    default_image = serializers.SerializerMethodField("get_image_url")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M")

    class Meta:
        model = Food
        fields = [
            "id",
            "name",
            "category",
            "prices",
            "min_price",
            "category_name",
            "description",
            "is_available",
            "images",
            "default_image",
            "uploaded_images",
            "avg_rating",
            "created_at",
            "modified_at",
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
        return obj.default_image.image.url

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
        images = validated_data.pop("uploaded_images", [])

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        # deleting all previous images
        for image in instance.images.all():
            image.delete()
        if instance.default_image:
            instance.default_image.delete()
        # creating images
        for i, image in enumerate(images):
            img_obj = FoodImage.objects.create(image=image, food=instance)
            # selecting first image as default

            if i == 0:
                instance.default_image = img_obj
        instance.save()
        return instance


class CFoodSerializerDetail(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField("get_category_name")
    prices = ListOfDecimalsField()  # custom field to parse form-data prices values
    min_price = MyDecimalField(read_only=True)
    images = FoodImageSerializer(many=True, read_only=True)
    default_image = serializers.SerializerMethodField("get_image_url")

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
        ]
        read_only_fields = ["__all__"]

    def get_category_name(self, obj):
        return obj.category.name

    def get_image_url(self, obj):
        return obj.default_image.image.url


class FoodSerializerMany(serializers.ModelSerializer):
    """this serializer is used in read only views - customers"""

    vendor_name = serializers.SerializerMethodField("get_vendor_name")
    min_price = MyDecimalField()
    default_image = serializers.SerializerMethodField("get_photo_url")

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
        ]

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name

    def get_photo_url(self, obj):
        return obj.default_image.image.url


class RatingSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField("get_user_name")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)

    class Meta:
        model = Rating
        fields = ["id", "user", "user_name", "comment", "created_at", "rating"]
        read_only_fields = ["id", "created_at", "user"]

    def get_user_name(self, obj):
        return obj.user.get_full_name()


class PublicVendorSerializer(serializers.ModelSerializer):
    """public vendor details"""

    foods = FoodSerializerMany(many=True, read_only=True)
    location = serializers.SerializerMethodField("get_location")

    class Meta:
        model = Vendor
        fields = [
            "id",
            "vendor_name",
            "active_hours",
            "location",
            "is_approved",
            "avg_rating",
            "rating_count",
            "foods",
        ]

    def get_location(self, obj):
        if obj.get_location():
            return obj.get_location().tuple  # json does not support point object


class FavItemSerializer(serializers.ModelSerializer):
    food_name = serializers.SerializerMethodField("get_food_name", read_only=True)

    class Meta:
        model = FavItem
        fields = ["favlist","food", "food_name"]

    def create(self, validated_data):
        favlist = FavList.objects.filter(self.context['favlist']).first()
        if not favlist:
            return serializers.ValidationError(detail="no_fav_list")
        validated_data["favlist"] = favlist
        return super().create(validated_data)

    def get_food_name(self, obj):
        return obj.food.name


class FavListSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField("get_user_name", read_only=True)

    class Meta:
        model = FavList
        fields = ["user", "user_name"]
        read_only_fields = ["user_name"]

    
    def get_user_name(self, obj):
        return obj.user.get_full_name()
