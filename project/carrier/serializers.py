from rest_framework import serializers
from .models import Carrier
from order.models import Order
from vendor.models import Vendor
class CarrierSerializer(serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)
    class Meta:
        model = Carrier
        fields = [
            "name",
            "user",
            "user_profile",
            "id_document",
            "vendor",
        ]
        read_only_fields = ["name"]

    def create(self, validated_data):
        """overriding to handle automatic vendor and name save"""
        vendor = Vendor.objects.get(id=self.context['vendor'])
        validated_data["name"] = self.context["name"]
        validated_data["vendor"] = vendor
        return super().create(validated_data)


class CarrierOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.SerializerMethodField("get_customer_name")

    class Meta:
        model = Order
        fields = [
            "customer_name",
            "total_items",
            "total_price",
            "status",
            "paid",
            "created",
        ]

    def get_customer_name(self, obj):
        return obj.user.first_name + obj.user.last_name
