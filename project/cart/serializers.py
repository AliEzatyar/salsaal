from rest_framework import serializers

from marketplace.serializers import MyDecimalField
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    name = serializers.ReadOnlyField(source="food.name")
    subtotal = serializers.SerializerMethodField("get_subtotal")
    price = MyDecimalField(read_only=True)
    image = serializers.SerializerMethodField("get_image_url")
    food_id = serializers.ReadOnlyField(source="food.id")

    class Meta:
        model = CartItem
        fields = ["id", "name", "price", "subtotal", "quantity",  "food_id","image"]
        read_only_fields = ["cart"]

    def get_subtotal(self, obj):
        return obj.get_total_price()

    def get_image_url(self, obj):
        return obj.food.image.url if obj.food.image else None


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField("calculate_total")
    total_items = serializers.SerializerMethodField("calculate_total_items")

    class Meta:
        model = Cart
        fields = ["items", "total_price", "total_items"]

    def calculate_total(self, obj):
        return obj.calculate_total()

    def calculate_total_items(self, obj):
        return obj.calculate_total_items()
