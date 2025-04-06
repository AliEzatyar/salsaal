from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField
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
