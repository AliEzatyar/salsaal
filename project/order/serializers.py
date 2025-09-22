from rest_framework.serializers import (
    ModelSerializer,
    PrimaryKeyRelatedField,
    SerializerMethodField,
)
from rest_framework import serializers
from carrier.serializers import CarrierSerializer
from marketplace.serializers import MyDecimalField
from carrier.utils import encrypt_32
from .models import Order, OrderItem
from accounts.models import User


class COrderItemSerializerMany(ModelSerializer):
    subtotal = serializers.SerializerMethodField("get_subtotal")
    food_name = serializers.SerializerMethodField("get_food_name")
    price = MyDecimalField()
    image = serializers.ReadOnlyField(source="food.image_url")
    id = serializers.ReadOnlyField(source="food.id")
    class Meta:
        model = OrderItem
        fields = ["id", "food_name", "quantity", "price", "subtotal","image"]
        read_only_fields = ["__all__"]

    def get_subtotal(self, obj):
        return obj.subtotal

    def get_food_name(self, obj):
        return obj.food_name


class COrderItemSerializer(ModelSerializer):
    subtotal = serializers.SerializerMethodField("get_subtotal")
    food_name = serializers.SerializerMethodField("get_food_name")
    image = serializers.ReadOnlyField(source="food.image_url")
    price = MyDecimalField()

    class Meta:
        model = OrderItem
        fields = ["image", "food_name", "quantity", "price", "subtotal"]
        read_only_fields = ["__all__"]

    def get_subtotal(self, obj):
        return obj.subtotal

    def get_food_name(self, obj):
        return obj.food_name



class COrderSerializer(ModelSerializer):
    user = PrimaryKeyRelatedField(read_only=True)
    items = COrderItemSerializerMany(many=True, read_only=True)
    vendor_name = serializers.ReadOnlyField(source="vendor.vendor_name")
    vendor_image = serializers.ReadOnlyField(source="vendor.image_url")
    total_price = MyDecimalField(read_only=True)
    carrier_name =  serializers.ReadOnlyField(source="carrier.user.full_name")
    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "status",
            "total_price",
            "paid",
            "payment_id",
            "is_credit",
            "created_at",
            "total_items",
            "carrier", # for live tracking if needed
            "carrier_name", # may be null
            "vendor",
            "vendor_name",
            "items",
            "otp",
            "payment_type",
            "vendor_image"
        ]
        # read_only_fields= ["paid","user","total_price","created_at","total_items","carrier","vendor","items","is_credit"]
        read_only_fields = ["__all__"]

    def create(self, validated_data):
        validated_data["user"] = User.objects.get(id=self.context["user"])
        return super().create(validated_data)

    def get_image_url(self,obj):
        return 

class COrderSerializerLessDetail(ModelSerializer):
    vendor_image = serializers.ReadOnlyField(source="vendor.image_url")
    total_price = MyDecimalField(read_only=True)
    vendor_name = serializers.ReadOnlyField(source="vendor.vendor_name")
    # items_pair = serializers.SerializerMethodField("get_items")
    items = COrderItemSerializerMany(many=True, read_only=True)

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
            # "items_pair",
            "items"
            
        ]

    # def get_items(self,obj):
    #     """this is used in orders list for review """
    #     return [(item.food.id,item.food.name) for item in obj.items.all()]

class VOrderItemSerializer(ModelSerializer):
    food_name = serializers.SerializerMethodField("get_food_name")
    total_price = serializers.SerializerMethodField("get_total_price")

    class Meta:
        model = OrderItem
        fields = ["food_name", "quantity", "total_price"]

    def get_food_name(self, obj):
        return obj.food_name

    def get_total_price(self, obj):
        return obj.subtotal

class VOrderSerializerLessDetail(ModelSerializer):
    total_price = MyDecimalField(read_only=True)

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
    items = VOrderItemSerializer(read_only=True, many=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:", read_only=True)
    total_price = MyDecimalField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_name",
            "total_items",
            "total_price",
            "status",
            "paid",
            "payment_id",
            "created_at",
            "carrier",
            "items",
        ]
        read_only_fields = ["id", "created_at"]

    def get_customer_name(self, obj):
        return obj.user.first_name + obj.user.last_name

