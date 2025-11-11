from django.urls import reverse
from carrier.models import CARRIER_STATUS_CHOICES
from carrier.utils import decrypt_32
from order.utils import get_order_delivery_tries_key, start_payment_session
from vendor.utils import get_vendor_carriers_key
from .serializers import (
    COrderSerializer,
    COrderSerializerLessDetail,
    OrderItemSerializerLessDetail,
)
from django.contrib.gis.geos import Point

from cart.models import CartItem
from .models import (
    MAX_ORDER_DELIVERY_TRIES_COUNT,
    ORDER_DELIVERY_ATTEPMTS_DELAY,
    VALID_PAYMENT_TYPES,
    ORDER_DELIVERY_OTP_EXPIRATION,
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
)
from django.utils.translation import activate as activate_language
from django.utils.translation import deactivate as deactivate_language
from live.utils import send_notification
from order.utils import create_payment_session
from django.conf import settings


class OrderViewSet(viewsets.ModelViewSet):
    """
    OrderViewSet is a Django REST Framework viewset that provides CRUD operations for managing orders.
    This viewset allows users to:
    - List their orders with limited details.
    - Create new orders from their cart, including validation and notification to vendors.
    - Cancel waiting orders.
    Attributes:
        http_method_names (list): Allowed HTTP methods for this viewset.
        serializer_class (class): Serializer class used for order serialization.
    Methods:
        get_queryset():
            Returns a queryset of orders filtered by the current user's ID.
        list(request, *args, **kwargs):
            Returns a list of orders for the current user with limited details.
        create(request, *args, **kwargs):
            Creates a new order from the user's cart, updates user location, and handles notifications.
        cancel(request):
            Cancels all waiting orders for the current user and notifies the respective vendors.
        get_serializer_context():
            Returns the context for the serializer, including the current user's ID.
    """

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
            try:
                float(lat)
                float(lon)
            except ValueError:
                return Response(
                    {"detail": "provide_correct_location"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user_profile = request.user.profile
            user_profile.latitude = str(lat)
            user_profile.longitude = str(lon)
            user_profile.save()
        else:
            return Response(
                {"detail": "provide_correct_location"},
                status=status.HTTP_400_BAD_REQUEST,
            )

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
            count = r.get(f"user:{request.user.id}:waiting")
            print(count, "redis count before increment")
            if count:
                count = json.loads(count)
            else:
                count = 0
            if count >= 1:
                return Response(
                    {"detail": "order_already_in_process"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            r.incrby(f"user:{request.user.id}:waiting", 1)

            previouse_preparing_orders_count = Order.objects.filter(
                user=request.user,
                status__in=(
                    ORDER_STATUS_CHOICES[2][0],
                    ORDER_STATUS_CHOICES[1][0],
                    ORDER_STATUS_CHOICES[3][0],
                ),
                vendor__id=vendor_id,
            ).count()
            if previouse_preparing_orders_count > MAX_PREPARING_ORDERS_COUNT:
                r.delete(f"user:{request.user.id}:waiting")
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
                order.destination = Point(float(lat), float(lon), srid=4326)
                order.save()
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
                    f"pub:vendor:{order.vendor.user.id}",
                    json.dumps(
                        {
                            "type": "NEW_ORDER",
                            "data": safe_data,
                        }  # vendor app should extract order id and subscribe to --order room
                    ),
                )
                r.delete(f"user:{request.user.id}:waiting")

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
    AcceptRejectOrderView
    Handle buyer confirmation/acceptance of an order via POST. Expected input:
    - order_id (required): ID of the Order to accept.
    - payment_type (required): one of VALID_PAYMENT_TYPES.
    - transaction_id (optional): required when payment_type == VALID_PAYMENT_TYPES[1][0] (online/Hesab Pay).
    Behavior:
    - Enforces IsAuthenticated and IsBuyer permissions and checks object permissions for the order.
    - Only allows transition when order.status is in the allowed waiting/preparing states.
    - Validates payment_type and handles three payment flows:
        - Non-reward payments: increment or create a Reward for the user based on vendor.reward_percentage.
        - Reward payments (VALID_PAYMENT_TYPES[2][0]): deduct from existing Reward; refuses if insufficient funds.
        - Online/Hesab Pay (VALID_PAYMENT_TYPES[1][0]): requires transaction_id and marks order as paid.
    - Uses an atomic transaction to update rewards, order.payment_type, transaction_id, paid flag, and set order.status to preparing.
    - Clears the buyer's cart, publishes an ORDER_UPDATE event to Redis (pub:order:<order_id>), and creates a Notification for the vendor.
    - Activates the buyer's preferred language briefly when creating the notification.
    Responses (not exhaustive):
    - 200/204: success (empty Response returned on success).
    - 400: invalid_payment_type or missing transaction_id.
    - 403: order_not_waiting_state or ineffecient_amount (insufficient reward balance).
    - 404: Order not found.
    - 501: unexpected server error.
    Notes:
    - Performs rounding when computing reward amounts.
    - Side effects: updates Reward and Order records, clears cart, publishes to Redis, creates Notification.
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
                response_data = {}
                if payment_type == VALID_PAYMENT_TYPES[1][0]:  # if Hesab Pay
                    items = OrderItemSerializerLessDetail(order.items)
                    session_url = start_payment_session(items.data, order_id)
                    order.is_epay = True
                    response_data['payment_session_url'] = session_url
                    # transaction_id = data.get("transaction_id", None)
                    # if not transaction_id:
                    #     return Response(
                    #         {"detail": "no_transaction_id"},
                    #         status=status.HTTP_400_BAD_REQUEST,
                    #     )
                    # order.transaction_id = transaction_id
                    # order.paid = True
                    
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
    SetOrderStateDelivered
    Handle POST requests from a carrier to mark an order as delivered. Expects encrypted
    'id' (order id) and 'pass' (OTP) in request.data; decrypts and validates the OTP,
    enforces max delivery attempts via Redis, and performs the state transition inside
    an atomic transaction. Side effects include clearing the user's cart, marking the
    order delivered/paid, freeing the carrier, updating vendor carrier counts in Redis,
    deleting the OTP, creating notifications for customer and vendor, and publishing a
    vendor websocket message.
    Permissions: IsAuthenticated, IsBuyer, IsOrderCarryingState.
    Responses: 202 Accepted on success; 403 for invalid/expired OTP or permission issues;
    404 if order not found; 400 on invalid OTP input; 501 for unknown errors.
    """

    permission_classes = [permissions.IsAuthenticated, IsBuyer, IsOrderCarryingState]

    def post(self, *args, **kwargs):
        """carrier sets order status -delivered-"""
        data = self.request.data
        order_id = data.get("id")
        input_otp = data.get("pass")
        print(data)
        try:
            order_id = int(decrypt_32(order_id))
            otp = int(decrypt_32(input_otp))
            order = Order.objects.get(id=order_id)
            # check if the customer owns this order
            self.check_object_permissions(self.request, order)
            # check if otp is correct
            self.request.user.cart.items.all().delete()
            user = order.user
            otp = UserOtp.objects.filter(user=user, otp=otp).first()
            # setting max tries
            order_delivery_tries_key = get_order_delivery_tries_key(order_id)
            tries = r.get(order_delivery_tries_key)
            if tries:
                tries = json.loads(tries)
            else:
                tries = 0
            r.incrby(order_delivery_tries_key, 1)
            if (
                tries > MAX_ORDER_DELIVERY_TRIES_COUNT
                or not otp
                or otp.is_expired(expire=ORDER_DELIVERY_OTP_EXPIRATION)
            ):
                r.expire(order_delivery_tries_key, ORDER_DELIVERY_ATTEPMTS_DELAY)
                return Response(
                    {"detail": "otp_invalid_or_expired"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            with atomic():
                # setting order in submited state and carrier in free state
                order.status = ORDER_STATUS_CHOICES[4][1]  # delivered
                order.carrier.status = CARRIER_STATUS_CHOICES[0][0]  # free
                order.carrier.save()
                order.paid = True
                otp.delete()
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
    """
    ReOrder API view for handling reordering of previous orders.
    This view allows authenticated users with the 'IsBuyer' permission to reorder items
    from a previous order. The user must provide the 'order_id' of the order they wish
    to reorder. If the order exists and the user has permission to access it, the items
    from the previous order will be added to the user's cart.
    Methods:
        post: Handles the POST request to reorder items from a previous order.
    Request Body:
        - order_id (str): The ID of the previous order to be reordered.
    Responses:
        - 200 OK: If the items are successfully added to the cart.
        - 400 Bad Request: If 'order_id' is not provided.
        - 500 Internal Server Error: If an error occurs while processing the order.
    """

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


class RedirectPaymentSuccess(views.APIView):
    """
    this view is called by hesab pay and redirects success url to mobile app and sends session id.
    """

    def get(self, *args, **kwargs):
        body = self.request.body
        params = self.request.query_params
        print(body, "this was body")
        print(params, "this was params")
        session_id = params.get("session_id")
        app_link = f"zayton://payment/success?session_id={session_id}"
        response = Response(status=status.HTTP_302_FOUND)
        response["Location"] = app_link
        return response


class RedirectPaymentFailure(views.APIView):
    """
    this view redirects success url to mobile app and sends session id.
    """

    def get(self, *args, **kwargs):
        body = self.request.body
        params = self.request.query_params
        print(body, "this was gateway response body")
        print(params, "this was gateway response params")
        session_id = params.get("session_id")
        app_link = f"zayton://payment/failure?session_id={session_id}"
        response = Response(status=status.HTTP_302_FOUND)
        response["Location"] = app_link
        return response


class HesabPayWebhook(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        data = request.data
        print("HesabPay webhook data:", data)
        success = data.get("success")
        transaction_id = data.get("transaction_id")
        memo = data.get("memo")

        if success == "true" and memo and transaction_id:
            try:
                # Assuming memo is in the format "ORDER-123"
                order_id_str = memo.split("-")[-1]
                order_id = int(order_id_str)

                order = Order.objects.get(id=order_id)

                with atomic():
                    order.paid = True
                    order.transaction_id = transaction_id
                    order.save()

                # Notify vendor and customer if needed
                # Example: send a websocket message or a push notification
                r.publish(
                    f"pub:order:{order.id}",
                    json.dumps(
                        {
                            "type": "PAYMENT_CONFIRMED",
                            "data": {"order_id": order.id, "paid": True},
                        }
                    ),
                )
                print(f"Order {order_id} marked as paid.")
                return Response(status=status.HTTP_200_OK)

            except (Order.DoesNotExist, ValueError, IndexError) as e:
                print(f"Error processing webhook: {e}")
                return Response(
                    {"detail": "Invalid order ID in memo"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return Response(
            {"detail": "Invalid payload"}, status=status.HTTP_400_BAD_REQUEST
        )
