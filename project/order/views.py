from .serializers import OrderSerializer, OrderItemSerializerMany, OrderItemSerializer
from cart.models import CartItem
from .models import Order, OrderItem, ORDER_STATUS_CHOICES
from rest_framework.decorators import action
from rest_framework import viewsets, views, status
from rest_framework.response import Response
from marketplace.utils import BoughtTogetherRecommender
from live.models import Notification
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
import json

"""Order API Views"""


class OrderViewSet(viewsets.ModelViewSet):
    """this view enables order create/edit/del by customer"""

    http_method_names = ["delete", "post", "get"]
    serializer_class = OrderSerializer

    @action(detail=False, methods=["delete"], url_path="cancel")
    def cancel(self, request):
        """this cancells only waiting orders"""
        orders = Order.objects.filter(
            user=request.user, status=ORDER_STATUS_CHOICES[1][1]
        )
        print("cacneling", orders)
        for order in orders:
            order.cancel_order()
        return Response(status=status.HTTP_200_OK)

    def get_queryset(self):
        """overrding it to get orders of specific user"""
        user_id = self.request.user.id
        new_queryset = Order.objects.filter(
            user_id=int(user_id),
            status__in=[
                ORDER_STATUS_CHOICES[1][0],  # waiting
                ORDER_STATUS_CHOICES[2][0],  # preparing
                ORDER_STATUS_CHOICES[3][0],  # carrying
            ],
        )
        return new_queryset

    def create(self, request, *args, **kwargs):
        """overriding this method to create order items from cart and calc totals"""
        data = dict(
            request.data
        )  # auto json to dict since restframework request object
        cart = request.user.cart
        # setting vendor id
        if cart.calculate_total_items() < 1:
            return Response(
                {"error": "no item in cart"}, status=status.HTTP_400_BAD_REQUEST
            )
        vendor_id = CartItem.objects.filter(cart=cart).first().food.vendor.id
        data["vendor"] = vendor_id

        # creating the serializer
        serializer = self.get_serializer(data=data)

        if Order.objects.filter(
            user=request.user, status=ORDER_STATUS_CHOICES[1][1], vendor__id=vendor_id
        ).exists():
            # prevent duplicate order if user has one 'waiting' order already
            return Response(
                {"error": "order_already_in_process"}, status=status.HTTP_403_FORBIDDEN
            )

        serializer.is_valid(raise_exception=True)  # validating data
        self.perform_create(serializer)  # creating the order
        order = serializer.instance  # getting newly created order object by serializer
        order_items = []
        OrderItem.objects.filter(
            order=order
        ).delete()  # flush previous items and recreate new items
        pks = []
        # ----------------------- creating order item objects
        for item in CartItem.objects.filter(cart=cart).select_related("food__vendor"):
            order_item = OrderItem.objects.get_or_create(
                order=order,
                food=item.food,
                vendor=item.food.vendor,
                quantity=item.quantity,
                price=item.price,
            )[0]
            pks.append(item.food.id)
            order_items.append(order_item)
        # ------------------------ feeding recommender
        recommender = BoughtTogetherRecommender()
        recommender.update_together_bought(pks)
        order.calculate_total_price()  # setting total price field value
        order.set_total_items()  # setting total items amount field value

        # flushing the cart
        cart.items.all().delete()
        # ------------------------- creating the notification object
        safe_data = json.loads(
            json.dumps(
                serializer.data, cls=DjangoJSONEncoder
            )  # Converts Decimal -> float
        )
        notf = Notification.objects.create(
            title="Order Created",
            type="new_order",
            data=safe_data,
            object_id=order.id,
            ct=ContentType.objects.get_for_model(Order),
            to=order.vendor.id,
        )   
        response = Response(
            {"order":serializer.data,
             "notf_id":notf.id,
             },
            status=status.HTTP_201_CREATED,
        )
        return response

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user"] = self.request.user.id
        return context


class OrderItemListAPIView(views.APIView):
    """returns all orders of an"""

    def get(self, request, order_id):
        items = OrderItem.objects.filter(order_id=order_id)
        serializer = OrderItemSerializerMany(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderItemDetailAPIView(views.APIView):
    def get(self, request, item_id):
        item = OrderItem.objects.filter(id=item_id).first()
        if item:
            serializer = OrderItemSerializer(item)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"message": "no_object_found"}, status=status.HTTP_404_NOT_FOUND
        )
