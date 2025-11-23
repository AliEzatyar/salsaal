from rest_framework import serializers

from marketplace.serializers import CustomDecimalField
from .models import Cart, CartItem


class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer for individual cart items.

    Attributes:
        - name: The name of the food item.
        - subtotal: The total price for the cart item (quantity * price).
        - price: The price of the food item.
        - image: The image URL of the food item.
        - food_id: The ID of the food item.
    """
    name = serializers.ReadOnlyField(source="food.name")
    subtotal = serializers.SerializerMethodField("get_subtotal")
    price = CustomDecimalField(read_only=True)
    image = serializers.ReadOnlyField(source="food.image_url")
    food_id = serializers.ReadOnlyField(source="food.id")

    class Meta:
        model = CartItem
        fields = ["id", "name", "price", "subtotal", "quantity",  "food_id","image"]
        read_only_fields = ["cart"]

    def get_subtotal(self, obj):
        """
        Calculate the subtotal for the cart item.

        Args:
            obj: The cart item instance.

        Returns:
            The total price for the cart item.
        """
        return obj.total_price


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for the shopping cart.

    Attributes:
        - items: A list of cart items.
        - total_price: The total price of all items in the cart.
        - total_items: The total quantity of items in the cart.
    """
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField("calculate_total")
    total_items = serializers.SerializerMethodField("calculate_total_items")

    class Meta:
        model = Cart
        fields = ["items", "total_price", "total_items"]

    def calculate_total(self, obj):
        """
        Calculate the total price of the cart.

        Args:
            obj: The cart instance.

        Returns:
            The total price of all items in the cart.
        """
        return obj.calculate_total()

    def calculate_total_items(self, obj):
        """
        Calculate the total quantity of items in the cart.

        Args:
            obj: The cart instance.

        Returns:
            The total quantity of items in the cart.
        """
        return obj.calculate_total_items()
