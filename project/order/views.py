from carrier.models import CARRIER_STATUS_CHOICES
from carrier.utils import decrypt_32
from vendor.models import Vendor
from vendor.utils import get_vendor_carriers_key
from .serializers import (
    COrderSerializer,
    COrderSerializerLessDetail,
)
from cart.models import CartItem
from .models import (
    VALID_PAYMENT_TYPES,
    Order,
    OrderItem,
    ORDER_STATUS_CHOICES,
    MAX_PREPARING_ORDERS_COUNT,
    Reward,
)
from rest_framework.decorators import action
from rest_framework import viewsets, views, status, permissions
from rest_framework.response import Response
from marketplace.utils import BoughtTogetherRecommender
from live.models import Notification
from django.db.transaction import atomic
from django.core.serializers.json import DjangoJSONEncoder
import json
from live.serializers import NotificationSerializer
from django.utils.translation import activate, deactivate, gettext as _
from marketplace.utils import r
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from api.permissions import IsBuyer, IsOrderCarryingState
from accounts.models import (
    UserOtp,
    FOOD_DELIVERY_OTP_EXPIRATION,
)
from django.utils.translation import activate as activate_language
from django.utils.translation import deactivate as deactivate_language
from django.contrib.gis.geos import Point
from live.utils import send_notification

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
        ).prefetch_related("items__food")
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
        # updating user's location to latest area
        lat = data.get("latitude", None)
        lon = data.get("longitude", None)
        if lat and lon:
            user_profile = request.user.profile
            user_profile.latitude = str(lat)
            user_profile.longitude = str(lon)
            user_profile.save()
            print("user locaiton updated")

        cart = request.user.cart
        # setting vendor id
        if cart.calculate_total_items() < 1:
            return Response(
                {"detail": "cart_empty"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            vendor_id = CartItem.objects.filter(cart=cart).last().food.vendor.id
            # -------------------- deleting waiting orders
            previous_waiting_orders = Order.objects.filter(
                user=request.user,
                status=ORDER_STATUS_CHOICES[1][1],  # waiting
            )
            if len(previous_waiting_orders) > 0:
                previous_waiting_orders.delete()

            # preventing new order if it exceeds max preparing orders limit for user
            previouse_preparing_orders_count = Order.objects.filter(
                user=request.user,
                status=ORDER_STATUS_CHOICES[2][0],
                vendor__id=vendor_id,
            ).count()
            if previouse_preparing_orders_count > MAX_PREPARING_ORDERS_COUNT:
                # prevent duplicate order if user has one 'waiting' order already
                return Response(
                    {"detail": "order_already_in_process"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # --------------- validating and creating order
            data["vendor"] = vendor_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)  # validating data
            with atomic():
                self.perform_create(serializer)  # creating the order
                order = serializer.instance
                OrderItem.objects.filter(
                    order=order
                ).delete()  # flush previous items and recreate new items
                pks = []  # this list feeds recommender
                # ----------------------- creating order item objects
                for item in CartItem.objects.filter(cart=cart).select_related(
                    "food__vendor"
                ):
                    OrderItem.objects.create(
                        order=order,
                        food=item.food,
                        vendor=item.food.vendor,
                        quantity=item.quantity,
                        price=item.price,
                    )
                    pks.append(item.food.id)

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
                    description=None,
                    target_id=order.id,
                )
                deactivate()
                # ----- sending notification to vendor's room
                send_notification.delay(
                    order.vendor.user.id,
                    notf.title,
                    body=notf.description,
                    data={"order_id": order.id},
                )
                r.publish(
                    f"pub:vendor:{order.vendor.id}",
                    json.dumps(
                        {
                            "type": "NEW_ORDER",
                            "data": NotificationSerializer(notf).data,
                        }  # vendor app should extract order id and subscribe to --order room
                    ),
                )

            # ------------------------ feeding recommender
            recommender = BoughtTogetherRecommender()
            recommender.update_together_bought(pks)
            response = Response(
                {
                    "order_id": order.id
                },  # buyer account uses to subscribe to `order` room for further things
                status=status.HTTP_201_CREATED,
            )
            return response
        except Exception as e:
            print("error in creating order", e)
            Order.objects.filter(
                user=request.user,
                status=ORDER_STATUS_CHOICES[1][1],
            ).delete()
            return Response(
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["delete"], url_path="cancel")
    def cancel(self, request):
        """this cancells only waiting orders"""
        orders = Order.objects.filter(
            user=request.user,
            status__in=[ORDER_STATUS_CHOICES[1][1], ORDER_STATUS_CHOICES[2][1]],
        )
        if len(orders) > 0:
            with atomic():
                for order in orders:
                    order.cancel_order()
                activate(request.user.profile.pf_lang)
                notf = Notification.objects.create(
                    title=_("order has been cancelled by buyer!"),
                    type="ORDER_CANCELLED",
                    data={},
                    receiver=order.vendor.user,
                    target_id=order.id,
                )
                deactivate()
                # ----- sending notification to vendors room using redis
                send_notification.delay(
                    order.vendor.user.id, notf.title, body=notf.description
                )

                r.publish(
                    f"pub:vendor:{order.vendor.id}",
                    json.dumps(
                        {
                            "type": "ORDER_CANCELLED",
                            "data": {"orderId": order.id},
                        }  # vendor app should extract order id and subscribe to --order room
                    ),
                )
                # ----- deleting vendor status in redis
                key = f"order:${order.id}:status"
                r.delete(key)
        return Response(status=status.HTTP_200_OK)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user"] = self.request.user.id
        return context


class AcceptRejectOrderView(views.APIView):
    """
    THis view enables a customer to finalize order. It adjusts order status appropriately.
    """

    permission_classes = [IsAuthenticated, IsBuyer]

    def post(self, *args, **kwargs):
        data = self.request.data
        order_id = data.get("order_id", None)
        event_data = None
        try:
            order = Order.objects.get(id=order_id)
            # check if this user owns the order
            self.check_object_permissions(self.request, order)
            # only 'waiting' order can be set to preparing
            if not order.status in [
                ORDER_STATUS_CHOICES[1][0],  # waiting
                ORDER_STATUS_CHOICES[2][0],  # preparing
            ]:

                print("order  not wiaing preparing or waiting......", order_id)
                return Response(
                    {"detail", "order_not_waiting_state"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # checking if payment type is correct
            payment_type = data.get("payment_type", None)
            if not payment_type or not payment_type in [
                i[0] for i in VALID_PAYMENT_TYPES
            ]:
                return Response(
                    {"detail": "invalid_payment_type"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            # ------------checking if payment is reward + incrementing reward amount
            existing_reward = Reward.objects.filter(
                vendor__id=order.vendor.id, user=self.request.user
            ).first()
            with atomic():
                # payment type other than reward -> increment reward
                if payment_type != VALID_PAYMENT_TYPES[2][0]:
                    if existing_reward:
                        print("reward existed before")
                        existing_reward.amount += round(
                            (order.vendor.reward_percentage * float(order.total_price))
                            / 100
                        )
                        existing_reward.save()
                    else:
                        if order.vendor.reward_percentage > 0:
                            print("creating new reward")
                            reward_to_add = round(
                                (
                                    order.vendor.reward_percentage
                                    * float(order.total_price)
                                )
                                / 100
                            )
                            Reward.objects.create(
                                vendor=order.vendor,
                                user=self.request.user,
                                amount=reward_to_add,
                            )
                # payment type `reward` -> deduct reward
                else:
                    print("type reward paymnet")
                    # deducting reward and setting as paid
                    if not existing_reward or existing_reward.amount < float(
                        order.total_price
                    ):
                        return Response(
                            {
                                "detail": "ineffecient_amount",
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    existing_reward.amount -= float(order.total_price)
                    order.paid = True
                    existing_reward.save()

                # -------------- setting order payment type
                order.payment_type = payment_type
                # Online Payment
                if payment_type == VALID_PAYMENT_TYPES[1][0]:  # if Hesab Pay
                    payment_id = data.get("payment_id", None)
                    if not payment_id:
                        return Response(
                            {"detail": "no_payment_id"},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    order.payment_id = payment_id
                    order.paid = True
                order.status = ORDER_STATUS_CHOICES[2][1]  # preparing/execution
                order.save()
                event_data = {
                    "accepted": True,
                    "payment_type": payment_type,
                    "order_id": order_id,
                }
                self.request.user.cart.clear()
                # sendig order updates to vendor
                r.publish(
                    f"pub:order:{order.id}",
                    json.dumps(
                        {
                            "type": "ORDER_UPDATE",
                            "data": event_data,
                        }
                    ),
                )

            # creating notification for the user
            activate_language(self.request.user.profile.pf_lang)
            Notification.objects.create(
                title=_("Order Set Preparing"),
                description=_("your order is being prepared"),
                type="ORDER_SET_PREPARING",
                data={},
                receiver=order.vendor.user,
                target_id=order.id,
            )
            deactivate_language()

            return Response()

        except Order.DoesNotExist:
            print("order not found!")
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print("error in ar-order:", e.args, e)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class SetOrderStateDelivered(views.APIView):
    """
    This view is only accessible via customer account, it proves whether
    a customer (indirectly-by-scanning) is the owner of order and valid Food has reached it.
    """

    permission_classes = [permissions.IsAuthenticated, IsBuyer, IsOrderCarryingState]

    def post(self, *args, **kwargs):
        """carrier sets order status -delivered-"""
        data = self.request.data
        order_id = data.get("id")
        input_OTP = data.get("pass")
        print(data)
        try:
            order_id = int(decrypt_32(order_id))
            otp = int(decrypt_32(input_OTP))
            order = Order.objects.get(id=order_id)
            # check if the customer owns this order
            self.check_object_permissions(self.request, order)
            # check if otp is correct
            self.request.user.cart.items.all().delete()
            user = order.user
            OTP = UserOtp.objects.filter(user=user, otp=otp).first()
            if not OTP:
                return Response({"detail": "otp_incorrect"}, status=400)
            if OTP.is_expired(expire=FOOD_DELIVERY_OTP_EXPIRATION):
                return Response({"detail": "otp_expired"}, status=400)

            with atomic():
                # setting order in submited state and carrier in free state
                order.status = ORDER_STATUS_CHOICES[4][1]  # delivered
                order.carrier.status = CARRIER_STATUS_CHOICES[0][0]  # free
                order.carrier.save()
                order.paid = True
                OTP.delete()
                order.save()
                # ---------------- updating vendor's carriers in redis
                vendor = order.vendor
                vendor_carriers_key = get_vendor_carriers_key(vendor.id)
                b_c_c = r.hget(vendor_carriers_key, "b_c_c")  # busy carriers count
                b_c_c = int(b_c_c) - 1  # decrementing busy carrier's count
                r.hset(
                    vendor_carriers_key, "b_c_c", b_c_c
                )  # updating busy carriers count
                f_c_c = r.hget(vendor_carriers_key, "f_c_c")
                f_c_c = int(f_c_c) + 1  # incrementing free carrier's count
                r.hset(vendor_carriers_key, "f_c_c", f_c_c)
                # --------------- creating notification of order delivery for vendor
                profile = vendor.user.profile
                activate_language(profile.pf_lang)
                # notification for customer
                Notification.objects.create(
                    title=_("Order Delivered"),
                    description=_("Your order has been delivered successfully."),
                    type="ORDER_DELIVERED",
                    receiver=order.user,
                    target_id=order.id,
                )
                # notificaiton for vendor + send by websocket
                notf_vendor = Notification.objects.create(
                    title=_("Order Delivered"),
                    description=_(f"Order {order_id} delivered successfully."),
                    type="ORDER_DELIVERED",
                    receiver=order.vendor.user,
                    data={"order_id": order_id},
                    target_id=order.id,
                )
                deactivate_language()
                r.publish(
                    f"pub:vendor:{vendor.id}",
                    json.dumps(
                        {
                            "type": "ORDER_UPDATE",
                            "data": NotificationSerializer(notf_vendor).data,
                        }
                    ),
                )

            return Response(
                status=status.HTTP_202_ACCEPTED,
            )
        except Order.DoesNotExist:
            return Response({"detail": "no_macthing_order"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"detail": "invalid_otp"}, status=400)
        except PermissionDenied:
            return Response(
                {"detail": "not_allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            print("error:", e, e.args)
            return Response(
                {"detail": "uknown error occured"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )


class ReOrder(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsBuyer]

    def post(self, *args, **kwargs):
        data = self.request.data
        order_id = data.get("order_id", None)
        # case where user wants to order again
        if order_id:
            try:
                previous_order = Order.objects.get(id=order_id)
                self.check_object_permissions(self.request, previous_order)
                # clearing
                user_cart = self.request.user.cart
                user_cart.clear()
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
