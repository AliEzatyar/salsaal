from rest_framework import viewsets, views
from rest_framework import status
from order.models import Order
from .serializers import OrderItemSerializer, OrderSerializer
from rest_framework.views import APIView
from rest_framework.decorators import action
from django.http.response import JsonResponse
from rest_framework.response import Response
from ..models import OrderItem
from cart.models import Cart, CartItem


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        order.cancel_order()
        return JsonResponse({"saved": True})

    def create(self, request, *args, **kwargs):
        """overriding this method to create order items from cart and calc totals"""
        data = request.data  # auto json to dict since restframework request object
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)  # validating data
        self.perform_create(serializer)  # creating the order
        order = serializer.instance  # getting newly created order object by serializer
        cart = request.user.cart
        order_items = []
        OrderItem.objects.filter(
            order=order
        ).delete()  # flush previous items and recreate new items
        # creating order item objects
        for item in CartItem.objects.filter(cart=cart).select_related(
            "product__vendor"
        ):
            order_item = OrderItem.objects.get_or_create(
                order=order,
                product=item.product,
                vendor=item.product.vendor,
                quantity=item.quantity,
                price=item.product.price,
            )[0]
            order_items.append(order_item)
        order.calculate_total_price()  # setting total price field value
        order.set_total_items()  # setting total items amount field value
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrderItemListAPIView(views.APIView):

    def get(self, request, order_id):
        items = OrderItem.objects.filter(order_id=order_id)
        serializer = OrderItemSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderItemDetailAPIView(views.APIView):
    def get(self, request, item_id):
        item = OrderItem.objects.filter(id=item_id).first()
        if item:
            serializer = OrderItemSerializer(item)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response({'message':'no_object_found'},status=status.HTTP_404_NOT_FOUND)