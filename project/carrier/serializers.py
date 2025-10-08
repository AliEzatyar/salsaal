from rest_framework import serializers

from order.serializers import COrderItemSerializer
from .utils import encrypt_32
from marketplace.serializers import MyDecimalField
from order.models import Order
from .models import Carrier


class CarrierSerializer(serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)
    name = serializers.ReadOnlyField(source="user.full_name")
    class Meta:
        model = Carrier
        fields = [
            "id",
            "is_active",
            "vendor",
            "user",
            "user_profile",
            "id_document",
            "name",
        ]
        read_only_fields = ["id", "user", "user_profile", "email", "vendor", "name"]


class CarrierOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source="user.full_name")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)
    total_price = MyDecimalField(read_only=True)
    id = serializers.SerializerMethodField("get_id")
    otp = serializers.SerializerMethodField("get_otp")
    items = COrderItemSerializer(many=True)
    # customer_profile = serializers.ReadOnlyField(source="user.profile.picture.url")
    customer_profile = serializers.SerializerMethodField("get_customer_picture")
    destination = serializers.SerializerMethodField("get_destination")

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "total_items",
            "total_price",
            "delivery_cost",
            "status",
            "paid",
            "created_at",
            "user",
            "items",
            "otp",
            "destination",
            "customer_profile",
        ]
        read_only_fields = ["__all__"]

    def get_id(self, obj):
        return encrypt_32(obj.id)

    def get_customer_picture(self, obj):
        # print(obj.user.profile.picture.file)
        # print(hasattr(obj.user.profile.picture, "file"))
        return (
            obj.user.profile.picture.url
            if obj.user.profile.picture
            else None
        )
    def get_destination(self,obj):
        try:
            return reversed(list(obj.destination))
        except:
            return 
    def get_otp(self, obj):
        return encrypt_32(obj.otp)


class CarrierOrderSerializerMany(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source="user.full_name")
    total_price = MyDecimalField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "total_price",
            "created_at",
        ]
        read_only_fields = ["__all__"]
