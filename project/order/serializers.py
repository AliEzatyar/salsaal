from rest_framework.serializers import (
    ModelSerializer,
    PrimaryKeyRelatedField,
    SerializerMethodField,
)
from rest_framework import serializers
from .models import Order, OrderItem
from accounts.models import User


class OrderSerializer(ModelSerializer):
    user = PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Order
        fields = "__all__"

    def create(self, validated_data):
        validated_data["user"] = User.objects.get(id=self.context["user"])
        
        return super().create(validated_data)


class OrderItemSerializer(ModelSerializer):
    class Meta:
        model = OrderItem
        fields = "__all__"


class VOrderItemSerializer(ModelSerializer):
    food_name = serializers.SerializerMethodField("get_food_name")
    total_price = serializers.SerializerMethodField("get_total_price")

    class Meta:
        model = OrderItem
        fields = ["food_name", "quantity", "total_price"]

    def get_food_name(self, obj):
        return obj.food_name

    def get_total_price(self, obj):
        return obj.total_price


class VOrderSerializer(ModelSerializer):
    customer_name = SerializerMethodField("get_customer_name")
    items = VOrderItemSerializer(read_only=True,many=True)

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

    def get_customer_name(self, obj):
        return obj.user.first_name + obj.user.last_name


class CarrierOrderSerializer(ModelSerializer):
    customer_name = SerializerMethodField("get_customer_name")

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
        ]

    def get_customer_name(self, obj):
        return obj.user.first_name + obj.user.last_name
