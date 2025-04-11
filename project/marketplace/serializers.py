from rest_framework import serializers
from vendor.models import Vendor

from marketplace.models import Product, Rating


class VProductSerializer(serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Product
        fields = "__all__"

    def create(self, validated_data):
        validated_data["vendor"] = Vendor.objects.get(id=self.context["vendor"])
        return super().create(validated_data)


class CProductSerializer(serializers.ModelSerializer):
    vendor_name = serializers.CharField(read_only=True, source="vendor.vendor_name")
    category_name = serializers.CharField(read_only=True,source='category.name')
    
    class Meta:
        model = Product
        fields = ['id','name','price','category_name','description','image','is_available','rating','existing_amount','vendor_name']
        read_only_fields = list(fields)

class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        exclude = ["object_id", "content_type"]
