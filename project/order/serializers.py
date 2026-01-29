from rest_framework.serializers import (
    ModelSerializer,
    PrimaryKeyRelatedField,
    SerializerMethodField,
)
from rest_framework import serializers
from marketplace.serializers import CustomDecimalField
from carrier.utils import encrypt_32
from .models import Order, OrderItem, ORDER_STATUS_CHOICES
from accounts.models import User
from marketplace.utils import uws_redis
from json import loads as jloads
from logging import getLogger
from django.utils.translation import gettext as _
from django.utils.translation import activate as activate_language
from django.utils.translation import deactivate as deactivate_language

logger = getLogger(__name__)


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
             "is_epay"
        ]


class VOrderSerializer(ModelSerializer):
    customer_name = SerializerMethodField("get_customer_name")
    items = VOrderItemSerializerDetail(read_only=True, many=True)
    total_price = CustomDecimalField(read_only=True)
    destination = SerializerMethodField("get_destination")
    user_phone = SerializerMethodField("get_phone")
    is_foreign = serializers.SerializerMethodField("get_is_foreign")
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
            "delivery_cost",
            "is_foreign",
            "is_epay"
        ]
        read_only_fields = ["id", "created_at"]

    def get_customer_name(self, obj):
        if obj.user:
            return obj.user.name

    def get_phone(self,obj):
        if obj.user:
            if obj.status in [ORDER_STATUS_CHOICES[2][0], ORDER_STATUS_CHOICES[3][0], ORDER_STATUS_CHOICES[4][0]]:
                return obj.user.phone_number
            else:
                activate_language(obj.vendor.user_profile.pf_lang)
                message = _("Accept Order to see phone number")
                deactivate_language()
                return message
    
    def get_is_foreign(self,obj):
        if obj.user and obj.extra_data:
            is_foreign = obj.extra_data.get("is_foreign",False)
            return is_foreign
        return False
            
    def get_destination(self, obj):
        if obj.status == ORDER_STATUS_CHOICES[3][0] and obj.carrier:
            raw = uws_redis.get(f"carrier_last_{obj.carrier.user.id}")
            if raw:
                last_location = jloads(raw)
                return [float(last_location["latitude"]), float(last_location["longitude"])]
        if obj.destination:
            return [obj.destination.x, obj.destination.y]
        return [obj.vendor.latitude, obj.vendor.longitude]
