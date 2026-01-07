from rest_framework.serializers import (
    ModelSerializer,
    PrimaryKeyRelatedField,
    SerializerMethodField,
)
from rest_framework import serializers
from marketplace.serializers import CustomDecimalField
from carrier.utils import encrypt_32
from .models import Order, OrderItem
from accounts.models import User


class COrderItemSerializerMany(ModelSerializer):
    subtotal = serializers.SerializerMethodField("get_subtotal")
    food_name = serializers.SerializerMethodField("get_food_name")
    price = CustomDecimalField()
    image = serializers.ReadOnlyField(source="food.image_url")
    id = serializers.ReadOnlyField(source="food.id")
    
    class Meta:
        model = OrderItem
        fields = ["id", "food_name", "quantity", "price", "subtotal", "image"]
        read_only_fields = ["__all__"]

    def get_subtotal(self, obj):
        return obj.subtotal

    def get_food_name(self, obj):
        return obj.food_name


class COrderItemSerializer(ModelSerializer):
    subtotal = serializers.SerializerMethodField("get_subtotal")
    food_name = serializers.SerializerMethodField("get_food_name")
    image = serializers.ReadOnlyField(source="food.image_url")
    price = CustomDecimalField()

    class Meta:
        model = OrderItem
        fields = ["image", "food_name", "quantity", "price", "subtotal"]
        read_only_fields = ["__all__"]

    def get_subtotal(self, obj):
        return obj.subtotal

    def get_food_name(self, obj):
        return obj.food_name


class OrderItemSerializerLessDetail(ModelSerializer):
    """used in online payment session creation"""

    name = serializers.ReadOnlyField(source="food.name")
    price = serializers.ReadOnlyField(source="subtotal")
    
    class Meta:
        model = OrderItem
        fields = ["id", "name", "price"]


class COrderSerializer(ModelSerializer):
    user = PrimaryKeyRelatedField(read_only=True)
    items = COrderItemSerializerMany(many=True, read_only=True)
    vendor_name = serializers.ReadOnlyField(source="vendor.vendor_name")
    vendor_image = serializers.ReadOnlyField(source="vendor.image_url")
    total_price = CustomDecimalField(read_only=True)
    carrier_name = serializers.ReadOnlyField(source="carrier.user.name")
    carrier = serializers.ReadOnlyField(source="carrier.user.id")
    customer_name = serializers.ReadOnlyField(source="user.name")
    is_carrier_online = SerializerMethodField("get_is_carrier_online")
    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "status",
            "total_price",
            "paid",
            "transaction_id",
            "created_at",
            "total_items",
            "carrier",  # for live tracking if needed
            "carrier_name",  # may be null
            "vendor",
            "vendor_name",
            "items",
            "otp",
            "payment_type",
            "vendor_image",
            "customer_name",
            "is_carrier_online",
        ]
        read_only_fields = ["__all__"]

    def create(self, validated_data):
        validated_data["user"] = User.objects.get(id=self.context["user"])
        return super().create(validated_data)

    def get_is_carrier_online(self,obj):
        if obj.carrier:
            return obj.carrier.is_online
        return False
        
class COrderSerializerLessDetail(ModelSerializer):
    """
    this serializer is used by customer  order objects
    less
    """

    vendor_image = serializers.ReadOnlyField(source="vendor.image_url")
    total_price = CustomDecimalField(read_only=True)
    vendor_name = serializers.ReadOnlyField(source="vendor.vendor_name")
    items = COrderItemSerializerMany(many=True, read_only=True)
    carrier = serializers.ReadOnlyField(source="carrier.user.id")
    is_carrier_online = SerializerMethodField("get_is_carrier_online")
    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "total_price",
            "created_at",
            "total_items",
            "vendor",
            "carrier",
            "vendor_image",
            "vendor_name",
            "items",
            "is_carrier_online",
        ]
    def get_is_carrier_online(self,obj):
        if obj.carrier:
            return obj.carrier.is_online
        return False

class VOrderItemSerializerDetail(ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ["food_name", "quantity", "subtotal", "price"]


class VOrderSerializerLessDetail(ModelSerializer):
    total_price = CustomDecimalField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "status",
            "total_price",
            "created_at",
            "total_items",
        ]


class VOrderSerializer(ModelSerializer):
    customer_name = SerializerMethodField("get_customer_name")
    items = VOrderItemSerializerDetail(read_only=True, many=True)
    total_price = CustomDecimalField(read_only=True)
    destination = SerializerMethodField("get_destination")
    user_phone = SerializerMethodField("get_phone")
    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "user_phone",
            "total_items",
            "total_price",
            "status",
            "paid",
            "transaction_id",
            "created_at",
            "carrier",
            "items",
            "destination",
            "items",
            "payment_type",
        ]
        read_only_fields = ["id", "created_at"]

    def get_customer_name(self, obj):
        if obj.user:
            return obj.user.name

    def get_phone(self,obj):
        if obj.user:
            return obj.user.phone_number
            
    def get_destination(self, obj):
        if obj.destination:
            return [obj.destination.x, obj.destination.y]
        return
