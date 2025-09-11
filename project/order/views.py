from .serializers import (
    COrderSerializer,
    COrderSerializerLessDetail,
    COrderItemSerializerMany,
    COrderItemSerializer,
)
from cart.models import CartItem
from .models import VALID_PAYMENT_TYPES, Order, OrderItem, ORDER_STATUS_CHOICES
from rest_framework.decorators import action
from rest_framework import viewsets, views, status, permissions
from rest_framework.response import Response
from marketplace.utils import BoughtTogetherRecommender
from live.models import Notification
from django.core.serializers.json import DjangoJSONEncoder
import json
from live.serializers import NotificationSerializer
from django.utils.translation import activate, deactivate, gettext as _
from marketplace.utils import r
from rest_framework.permissions import IsAuthenticated
from api.permissions import IsBuyer

"""Order API Views"""


class OrderViewSet(viewsets.ModelViewSet):
    """this view enables order create/edit/del by customer"""

    http_method_names = ["delete", "post", "get"]
    serializer_class = COrderSerializer

    def get_queryset(self):
        """overrding it to get orders of specific user"""
        user_id = self.request.user.id
        new_queryset = Order.objects.filter(
            user_id=int(user_id),
        )
        return new_queryset

    def list(self, request, *args, **kwargs):
        """overriden for less detail"""
        user_id = self.request.user.id
        queryset = self.filter_queryset(
            Order.objects.filter(
                user_id=int(user_id),
                status__in=[
                    ORDER_STATUS_CHOICES[4][0],  # waiting
                    ORDER_STATUS_CHOICES[2][0],  # preparing
                    ORDER_STATUS_CHOICES[3][0],  # carrying,
                ],
            ).only(
                "id",
                "status",
                "total_price",
                "paid",
                "created_at",
                "total_items",
                "vendor",
            )[
                :20
            ]
        )
        serializer = COrderSerializerLessDetail(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """overriding this method to create order items from cart and calc totals"""

        data = dict(
            request.data
        )  # auto json to dict since restframework request object

        cart = request.user.cart
        # setting vendor id
        if cart.calculate_total_items() < 1:
            return Response(
                {"detail": "cart_empty"}, status=status.HTTP_400_BAD_REQUEST
            )
        vendor_id = CartItem.objects.filter(cart=cart).first().food.vendor.id
        data["vendor"] = vendor_id

        # -------------   assigning the serializer value and creating order
        serializer = self.get_serializer(data=data)
        if Order.objects.filter(
            user=request.user, status=ORDER_STATUS_CHOICES[1][1], vendor__id=vendor_id
        ).exists():
            # prevent duplicate order if user has one 'waiting' order already
            return Response(
                {"detail": "order_already_in_process"}, status=status.HTTP_403_FORBIDDEN
            )

        serializer.is_valid(raise_exception=True)  # validating data
        self.perform_create(serializer)  # creating the order
        order = serializer.instance  # getting newly created order object by serializer
        OrderItem.objects.filter(
            order=order
        ).delete()  # flush previous items and recreate new items
        pks = []
        # ----------------------- creating order item objects
        for item in CartItem.objects.filter(cart=cart).select_related("food__vendor"):
            OrderItem.objects.create(
                order=order,
                food=item.food,
                vendor=item.food.vendor,
                quantity=item.quantity,
                price=item.get_price_after_discount,
            )
            pks.append(item.food.id)
        # flushing the cart
        # cart.items.all().delete()
        # ------------------------ feeding recommender
        recommender = BoughtTogetherRecommender()
        recommender.update_together_bought(pks)
        order.calculate_total_price()  # setting total price field value
        order.set_total_items()  # setting total items amount field value
        # ------------------------- creating the notification object
        profile = request.user.profile
        activate(profile.pf_lang)
        safe_data = json.loads(
            json.dumps(
                serializer.data, cls=DjangoJSONEncoder
            )  # Converts Decimal -> float
        )
        notf = Notification.objects.create(
            title=_("you have a new order!"),
            type="NEW_ORDER",
            data=safe_data,
            receiver=order.vendor.user,
        )
        deactivate()
        # ----- sending notification to vendors room using redis
        r.publish(
            f"pub:vendor:{order.vendor.id}",
            json.dumps(
                {
                    "type": "NEW_ORDER",
                    "data": NotificationSerializer(notf).data,
                }  # vendor app should extract order id and subscribe to --order room
            ),
        )
        response = Response(
            {
                "order_id": order.id
            },  # buyer account uses to subscribe to -order room for further things
            status=status.HTTP_201_CREATED,
        )
        return response

    @action(detail=False, methods=["delete"], url_path="cancel")
    def cancel(self, request):
        """this cancells only waiting orders"""
        orders = Order.objects.filter(
            user=request.user,
            status__in=[ORDER_STATUS_CHOICES[1][1], ORDER_STATUS_CHOICES[2][1]],
        )
        print("cacnelling", orders)
        for order in orders:
            order.cancel_order()
        return Response(status=status.HTTP_200_OK)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user"] = self.request.user.id
        return context


class OrderItemListAPIView(views.APIView):
    """returns all orders of an"""

    def get(self, request, order_id):
        items = OrderItem.objects.filter(order_id=order_id)
        serializer = COrderItemSerializerMany(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderItemDetailAPIView(views.APIView):
    def get(self, request, item_id):
        item = OrderItem.objects.filter(id=item_id).first()
        if item:
            serializer = COrderItemSerializer(item)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"message": "no_object_found"}, status=status.HTTP_404_NOT_FOUND
        )


class AcceptRejectOrderView(views.APIView):
    """
    THis view enables a vendor either accept or reject the new order. It adjusts order status appropriately.
    """

    permission_classes = [IsAuthenticated, IsBuyer]

    def post(self, *args, **kwargs):
        data = self.request.data
        order_id = data.get("order_id", None)
        event_data = None
        print(order_id, "this was order id sent to accep/rejec")
        try:
            order = Order.objects.get(id=order_id)
            # check if this user owns the order
            self.check_object_permissions(self.request, order)
            # only 'waiting' order can be set to preparing
            if not order.status in [
                ORDER_STATUS_CHOICES[1][0],
                ORDER_STATUS_CHOICES[2][0],
            ]:

                print("order  not wiaing preparing or waiting......", order_id)
                return Response(
                    {"detail", "order_not_waiting_state"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # order accepted -> set as preparing, send notification
            payment_type = data.get("payment_type", None)
            print(payment_type)
            if not payment_type or not payment_type in [
                i[0] for i in VALID_PAYMENT_TYPES
            ]:
                return Response(
                    {"detail": "invalid_payment_type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            order.payment_type = payment_type
            order.status = ORDER_STATUS_CHOICES[2][1]  # preparing/execution
            order.save()
            event_data = {
                "accepted": True,
                "payment_type": payment_type,
                "order_id": order_id,
            }
            self.request.user.cart.clear()

            # sendig order updates anyway
            r.publish(
                f"pub:order:{order.id}",
                json.dumps(
                    {
                        "type": "ORDER_UPDATE",
                        "data": event_data,
                    }
                ),
            )
            return Response()

        except Order.DoesNotExist:
            print("order not found!")
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print("error in ar-order:", e.args, e)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class ReOrder(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsBuyer]
    def get(self, *args, **kwargs):
        data = self.request.query_params
        order_id = data.get("order_id", None)
        # case where user wants to order again
        if order_id:
            try:
                previous_order = Order.objects.get(id=order_id)
                self.check_object_permissions(self.request, previous_order)
                user_cart = self.request.user.cart
                for item in previous_order.items.select_related("food"):
                    CartItem.objects.create(
                        cart=user_cart,
                        food=item.food,
                        price=item.price,
                        quantity=item.quantity,
                    )
                return Response()
            except Exception as e:
                print("error in re-order", e)
                pass
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(
            {"detail": "provide_order_id"}, status=status.HTTP_400_BAD_REQUEST
        )
