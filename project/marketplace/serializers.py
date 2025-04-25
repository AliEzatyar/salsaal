from decimal import Decimal, InvalidOperation
import json
from rest_framework import serializers
from vendor.models import Vendor

from marketplace.models import Category, Food, Rating

from rest_framework import serializers
from decimal import Decimal, InvalidOperation
import json

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
        return round(float(value),2)

"""serializers"""

class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ["name"]


class FoodSerializerDetail(serializers.ModelSerializer):
    """this serializer is used for vendor-only CRUD"""
    category_name = serializers.SerializerMethodField("get_category_name")
    prices = ListOfDecimalsField() # custom field to parse form-data prices values
    min_price = MyDecimalField(read_only=True)
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
            "image",
            "is_available",
            "rating",
            "created_at",
            "modified_at",
        ]
        read_only_fields = ["rating", "created_at", "modified_at","min_price","id"]

    def get_category_name(self, obj):
        return obj.category.name


    def create(self, validated_data):
        """setting the vendor and min price for the food"""        
        validated_data["vendor"] = Vendor.objects.get(id=self.context["vendor"])
        validated_data["min_price"] = min([x for x in validated_data["prices"]])
        return super().create(validated_data)


class FoodSerializerMany(serializers.ModelSerializer):
    """this serializer is used in read only views - customers"""
    vendor_name = serializers.SerializerMethodField("get_vendor_name")
    min_price = MyDecimalField()

    class Meta:
        model = Food
        fields = ["name","min_price", "prices", "image", "rating", "vendor_name"]

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        exclude = ["object_id", "content_type"]
