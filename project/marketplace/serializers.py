from rest_framework import serializers
from vendor.models import Vendor

from marketplace.models import Category, Food, Rating


class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ["name"]


class FoodSerializer(serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)
    vendor_name = serializers.SerializerMethodField("get_vendor_name")
    distance = serializers.SerializerMethodField("get_distance")

    class Meta:
        model = Food
        fields = "__all__"

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name

    def get_distance(self, obj):
        # obj.distance is a Distance object; convert to km/miles/etc.
        return obj.distance.km if hasattr(obj, "distance") else None

    def create(self, validated_data):
        validated_data["vendor"] = Vendor.objects.get(id=self.context["vendor"])
        return super().create(validated_data)


class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        exclude = ["object_id", "content_type"]
