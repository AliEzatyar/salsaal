from rest_framework.serializers import (
    ModelSerializer,
    PrimaryKeyRelatedField,
    SerializerMethodField,
)
from rest_framework import serializers
from .models import Order, OrderItem
from accounts.models import User


class OrderItemSerializerMany(ModelSerializer):
    subtotal = serializers.SerializerMethodField("get_subtotal")
    food_name = serializers.SerializerMethodField("get_food_name")
    class Meta:
        model = OrderItem
        fields = ["id","food_name", "quantity", "price","subtotal"]
        read_only_fields = ["__all__"]
        
    def get_subtotal(self, obj):
        return obj.subtotal

    def get_food_name(self, obj):
        return obj.food_name


class OrderItemSerializer(ModelSerializer):
    subtotal = serializers.SerializerMethodField("get_subtotal")
    food_name = serializers.SerializerMethodField("get_food_name")
    image = serializers.SerializerMethodField("get_image_url")

    class Meta:
        model = OrderItem
        fields = ["image","food_name", "quantity", "price","subtotal"]
        read_only_fields = ["__all__"]

    def get_subtotal(self, obj):
        return obj.subtotal

    def get_food_name(self, obj):
        return obj.food_name

    def get_image_url(self,obj):
        return obj.food.default_image.image.url


class OrderSerializer(ModelSerializer):
    user = PrimaryKeyRelatedField(read_only=True)
    items = OrderItemSerializerMany(many=True,read_only=True)
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
            "carrier",
            "vendor",
            "items",
        ]
        # read_only_fields= ["paid","user","total_price","created_at","total_items","carrier","vendor","items","is_credit"]
        read_only_fields = ["__all__"]
        
    def create(self, validated_data):
        validated_data["user"] = User.objects.get(id=self.context["user"])
        return super().create(validated_data)


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


class VOrderSerializer(ModelSerializer):
    customer_name = SerializerMethodField("get_customer_name")
    items = VOrderItemSerializer(read_only=True,many=True)
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M:",read_only=True)

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
            "items"
        ]
        read_only_fields = ["id","created_at"]

    def get_customer_name(self, obj):
        return obj.user.first_name + obj.user.last_name


class CarrierOrderSerializer(ModelSerializer):
    customer_name = SerializerMethodField("get_customer_name")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M",read_only=True)

    class Meta:
        model = Order
        fields = [
            "customer_name",
            "total_items",
            "total_price",
            "status",
            "paid",
            "is_credit",
            "created_at",
            "user",
            "vendor"
        ]
        read_only_fields = ['created_at',"user"]
        
    def get_customer_name(self, obj):
        return obj.user.first_name + obj.user.last_name
