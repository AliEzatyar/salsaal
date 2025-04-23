from rest_framework import serializers
from vendor.models import Vendor

from marketplace.models import Category, Food, Rating


class CategorySerializer(serializers.ModelSerializer):

    class Meta:
        model = Category
        fields = ["name"]


class FoodSerializerDetail(serializers.ModelSerializer):
    category_name = serializers.SerializerMethodField("get_category_name")
    
    class Meta:
        model = Food
        fields = ["name","price","category","category_name","description","image","is_available","rating","created_at","modified"]
        read_only_fields = ["rating","created_at","modified"]

    def get_category_name(self,obj):
        return obj.category.name

    def create(self, validated_data):
        validated_data["vendor"] = Vendor.objects.get(id=self.context["vendor"])
        return super().create(validated_data)


class FoodSerializerMany(serializers.ModelSerializer):
    vendor_name = serializers.SerializerMethodField("get_vendor_name")

    class Meta:
        model = Food
        fields = ["name","price","image","rating","vendor_name"]

    def get_vendor_name(self, obj):
        return obj.vendor.vendor_name




class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        exclude = ["object_id", "content_type"]
