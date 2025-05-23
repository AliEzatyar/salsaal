from rest_framework import serializers
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    food_name = serializers.ReadOnlyField(source="food.name")
    food_price = serializers.ReadOnlyField(source="food.min_price")
    subtotal = serializers.SerializerMethodField("get_subtotal")

    class Meta:
        model = CartItem
        fields = ["id","food_name","food_price","subtotal","quantity"]
        read_only_fields = ["cart"]

    def get_subtotal(self, obj):
        return obj.get_total_price()


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField("calculate_total")
    total_items = serializers.SerializerMethodField("calculate_total_items")
    created_at = serializers.DateTimeField(format="%Y-%m-%d %H:%M",read_only=True)

    class Meta:
        model = Cart
        fields = ["created_at",'modified_at',"items",'total_price','total_items']
        read_only_fields = ["created_at"]
    def calculate_total(self,obj):
        return obj.calculate_total()

    def calculate_total_items(self,obj):
        return obj.calculate_total_items()
