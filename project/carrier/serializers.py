from rest_framework import serializers

from order.serializers import COrderItemSerializer
from .utils import encrypt_32
from marketplace.serializers import CustomDecimalField
from order.models import Order
from .models import Carrier
from marketplace.utils import uws_redis
from json import loads as jloads

class CarrierSerializer(serializers.ModelSerializer):
    vendor = serializers.PrimaryKeyRelatedField(read_only=True)
    name = serializers.ReadOnlyField(source="user.name")
    image = serializers.ReadOnlyField(source="user_profile.image.url")
    phone_number = serializers.ReadOnlyField(source="user.phone_number")
    last_location = serializers.SerializerMethodField("get_last_location")
    class Meta:
        model = Carrier
        fields = [
            "id",
            "is_active",
            "is_online",
            "vendor",
            "user",
            "name",
            "image",
            "phone_number",
            "last_location"
        ]
        read_only_fields = ["id", "user", "name", "vendor", "image", "phone_number"]

    def get_last_location(self, obj):
        raw = uws_redis.get(f"carrier_last_{obj.user.id}")
        if raw:
            last_location = jloads(raw)
            return [float(last_location["latitude"]),
                float(last_location["longitude"])]
        return [obj.vendor.latitude, obj.vendor.longitude]

class CarrierOrderSerializer(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source="user.name")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M", read_only=True)
    total_price = CustomDecimalField(read_only=True)
    id = serializers.SerializerMethodField("get_id")
    otp = serializers.SerializerMethodField("get_otp")
    items = COrderItemSerializer(many=True)
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
        if obj.user:
            return obj.user.profile.picture.url if obj.user.profile.picture else None
        return None

    def get_destination(self, obj):
        if obj.destination:
            return [obj.destination.x, obj.destination.y]
        return

    def get_otp(self, obj):
        return encrypt_32(obj.otp)


class CarrierOrderSerializerMany(serializers.ModelSerializer):
    customer_name = serializers.ReadOnlyField(source="user.name")
    total_price = CustomDecimalField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "total_price",
            "created_at",
        ]
        read_only_fields = ["__all__"]
