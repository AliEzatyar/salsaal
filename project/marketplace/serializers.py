from rest_framework import serializers
from vendor.models import Vendor

from marketplace.models import Food, Rating


class FoodSerializer(serializers.ModelSerializer):
    vendor= serializers.PrimaryKeyRelatedField(read_only=True)
    vendor_name = serializers.SerializerMethodField('get_vendor_name')
    
    
    
    class Meta:
        model = Food
        fields = "__all__"


    def get_vendor_name(self,obj):
        return obj.vendor.vendor_name


    def create(self, validated_data):
        validated_data['vendor'] = Vendor.objects.get(id=self.context['vendor'])
        return super().create(validated_data)

class RatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rating
        exclude = ["object_id", "content_type"]
