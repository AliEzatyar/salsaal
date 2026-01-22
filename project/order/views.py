from carrier.models import CARRIER_STATUS_CHOICES
from carrier.utils import decrypt_32
from order.utils import (
    acquire_payment_lock,
    create_multi_vendor_payment,
    get_order_delivery_tries_key,
    get_order_payment_key,
    start_payment_session,
)
from multiVend.country.info import PLATFORM_ONLINE_PAYMENT_SHARE
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
    ORDER_DELIVERY_ATTEMPTS_DELAY,
    VALID_PAYMENT_TYPES,
    ORDER_DELIVERY_OTP_EXPIRATION,
    FailedMultiVendorPayment,
    Order,
    OrderItem,
    ORDER_STATUS_CHOICES,
    MAX_PREPARING_ORDERS_COUNT,
    Reward,
)
from rest_framework.decorators import action
from rest_framework import viewsets, views, permissions, status as rsp_status
from rest_framework.response import Response
from marketplace.utils import BoughtTogetherRecommender, haversine_distance
from live.models import Notification
from django.db.transaction import atomic
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.utils.translation import activate, deactivate, gettext as _
from marketplace.utils import r
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from api.permissions import IsBuyer, IsCustomer, IsOrderCarryingState
from accounts.models import (
    UserOtp,
)
from django.utils.translation import activate as activate_language
from django.utils.translation import deactivate as deactivate_language
from live.utils import push_notification
from logging import getLogger

logger = getLogger(__name__)


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
            * User's cart is not cleared here but in AcceptRejectOrderView upon order acceptance.
        cancel(request):
            Cancels all waiting orders for the current user and notifies the respective vendors.
        get_serializer_context():
            Returns the context for the serializer, including the current user's ID.
    """

    http_method_names = ["delete", "post", "get"]
    serializer_class = COrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsCustomer]

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
                    ORDER_STATUS_CHOICES[2][0],  # preparing
                    ORDER_STATUS_CHOICES[3][0],  # carrying
                    ORDER_STATUS_CHOICES[4][0],  # delivered
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
        # ----------------- updating user's location
        lat = data.get("latitude", None)
        lon = data.get("longitude", None)
        if lat and lon:
            try:
                float(lat)
                float(lon)
            except ValueError:
                return Response(
                    {"detail": "provide_correct_location"},
                    status=rsp_status.HTTP_400_BAD_REQUEST,
                )
            
            user_profile = request.user.profile
            user_profile.latitude = str(lat)
            user_profile.longitude = str(lon)
            user_profile.save()
            
        else:
            return Response(
                {"detail": "provide_correct_location"},
                status=rsp_status.HTTP_400_BAD_REQUEST,
            )
        # ----------------- validating cart has items
        cart = request.user.cart
        if cart.calculate_total_items() < 1:
            return Response(
                {"detail": "cart_empty"}, status=rsp_status.HTTP_400_BAD_REQUEST
            )
        try:
            # getting total and enforcing vendor
            vendor = CartItem.objects.filter(cart=cart).last().food.vendor
            # checking distance limit can be added here
            distance_km = haversine_distance(
                float(vendor.latitude),
                float(vendor.longitude),
                float(lat),
                float(lon),
            )
            # vendor max delivery distance check and if foreign, allow
            if distance_km < 200 and  distance_km > vendor.mdd :
                logger.warning(f"order creation attempt out of delivery zone for user {request.user.id} vendor {vendor.id} distance {distance_km} km.")
                return Response(
                    {"error": "OUT_OF_DELIVERY_ZONE",
                     "message":  "The delivery address is outside the restaurant delivery area."},
                    status=rsp_status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            total_price =  cart.calculate_total()
            if total_price < vendor.min_order_price:
                return Response(
                    {
                        "detail": "min_order_price_not_met",
                        "min_order_price": vendor.min_order_price,
                    },
                    status=rsp_status.HTTP_403_FORBIDDEN,
                )
            # getting vendor id
            vendor_id = vendor.id
            
            # -------------------- deleting waiting orders
            previous_waiting_orders = Order.objects.filter(
                user=request.user,
                status=ORDER_STATUS_CHOICES[1][1],  # waiting
            )
            if len(previous_waiting_orders) > 0:
                previous_waiting_orders.delete()

            # -------------- checking if user has reached limit of waiting orders
            waiting_orders_count = r.get(f"user:{request.user.id}:waiting")
            if waiting_orders_count:
                waiting_orders_count = json.loads(waiting_orders_count)
            else:
                waiting_orders_count = 0
            if waiting_orders_count >= 1:
                return Response(
                    {"detail": "order_already_in_process"},
                    status=rsp_status.HTTP_403_FORBIDDEN,
                )
            r.incrby(f"user:{request.user.id}:waiting", 1)
            # -------------- checking if user has reached limit of preparing orders
            previous_preparing_orders_count = Order.objects.filter(
                user=request.user,
                status__in=(
                    ORDER_STATUS_CHOICES[2][0],
                    ORDER_STATUS_CHOICES[1][0],
                    ORDER_STATUS_CHOICES[3][0],
                ),
                vendor__id=vendor_id,
            ).count()
            if previous_preparing_orders_count > MAX_PREPARING_ORDERS_COUNT:
                r.delete(f"user:{request.user.id}:waiting")
                # prevent duplicate order if user has one 'waiting' order already
                return Response(
                    {"detail": "order_already_in_process"},
                    status=rsp_status.HTTP_403_FORBIDDEN,
                )
            # --------------- data validating and creating new order
            data["vendor"] = vendor_id
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)  # validating data
            with atomic():
                self.perform_create(serializer)  # creating the order
                new_order = serializer.instance
                OrderItem.objects.filter(
                    order=new_order
                ).delete()  # flush previous items and recreate new items
                pks = []  # this list feeds recommender
                # ----------------------- creating order item objects
                for item in CartItem.objects.filter(cart=cart).select_related(
                    "food__vendor"
                ):
                    OrderItem.objects.create(
                        order=new_order,
                        food=item.food,
                        vendor=item.food.vendor,
                        quantity=item.quantity,
                        price=item.price,
                    )
                    pks.append(item.food.id)

                new_order.calculate_total_price()  # setting total price field value
                new_order.set_total_items()  # setting total items amount field value
                new_order.destination = Point(float(lat), float(lon), srid=4326)
                new_order.save()
                # ------------------------- creating notification for vendor
                profile = new_order.vendor.user.profile
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
                    receiver=new_order.vendor.user,
                    description=_("you have received a new order from a customer."),
                    target_id=new_order.id,
                )
                deactivate()
                # ------------- sending notification to vendor
                push_notification.delay(
                    new_order.vendor.user.id,
                    notf.title,
                    body=notf.description,
                    data={"order_id": new_order.id},
                )
                r.publish(
                    f"pub:vendor:{new_order.vendor.user.id}",
                    json.dumps(
                        {
                            "type": "NEW_ORDER",
                            "data": safe_data,
                        }
                    ),
                )
                r.delete(f"user:{request.user.id}:waiting")

            # ------------------------ feeding recommender
            recommender = BoughtTogetherRecommender()
            recommender.update_together_bought(pks)
            response = Response(
                {"order_id": new_order.id},
                status=rsp_status.HTTP_201_CREATED,
            )
            return response
        except Exception as e:
            logger.exception(f"error in creating order: {e}")
            Order.objects.filter(
                user=request.user,
                status=ORDER_STATUS_CHOICES[1][1],
            ).delete()
            return Response(
                status=rsp_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=False, methods=["delete"], url_path="cancel")
    def cancel(self, request):
        """this endpoint cancells only waiting orders for request user"""
        orders = Order.objects.filter(
            user=request.user,
            status__in=[
                ORDER_STATUS_CHOICES[1][1],  # waiting order
                ORDER_STATUS_CHOICES[2][1],  # preparing
            ],  # preparing order
        )[:1]
        
        if len(orders) > 0:
            with atomic():
                for order in orders:
                    order.cancel_order()
                activate(order.vendor.user_profile.pf_lang)
                notf = Notification.objects.create(
                    title=_("order has been cancelled by buyer!"),
                    type="ORDER_CANCELLED",
                    data={},
                    receiver=order.vendor.user,
                    target_id=order.id,
                )
                # ------------- sending notification to vendor
                push_notification.delay(
                    order.vendor.user.id, notf.title, body=_("We are sorry to inform you that the order has been cancelled."), data={"order_id": order.id}
                )

                deactivate()
                r.publish(
                    f"pub:vendor:{order.vendor.user.id}",
                    json.dumps(
                        {
                            "type": "ORDER_CANCELLED",
                            "data": {"orderId": order.id,
                                     "orderStatus": order.status},
                        }
                    ),
                )
        return Response(status=rsp_status.HTTP_200_OK)

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
    - transaction_id (optional): required when payment_type = VALID_PAYMENT_TYPES[1][0] (online/Hesab Pay).
    Behavior:
    - Enforces IsAuthenticated and IsBuyer permissions and checks object permissions for the order.
    - Only allows transition when order.status is in the allowed waiting states.
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
        payment_type = data.get("payment_type", None)
        try:
            order = Order.objects.get(id=order_id)
            # ------------- only 'waiting' order
            if not order.status == ORDER_STATUS_CHOICES[1][0]:
                return Response(
                    {"detail": "order_not_waiting_state"},
                    status=rsp_status.HTTP_403_FORBIDDEN,
                )
            # ------------- check if this user owns the order
            self.check_object_permissions(self.request, order)
            # ------------ validate payment type
            if not payment_type or not payment_type in [
                i[0] for i in VALID_PAYMENT_TYPES
            ]:
                return Response(
                    {"detail": "invalid_payment_type"},
                    status=rsp_status.HTTP_400_BAD_REQUEST,
                )
            existing_reward = Reward.objects.filter(
                vendor__id=order.vendor.id, user=self.request.user
            ).first()
            with atomic():
                # --------- payment type is reward -> deduct reward and set as payed
                if payment_type == VALID_PAYMENT_TYPES[2][0]:
                    if not existing_reward or existing_reward.amount < float(
                        order.total_price
                    ):
                        return Response(
                            {"detail": "ineffecient_amount"},
                            status=rsp_status.HTTP_403_FORBIDDEN,
                        )
                    existing_reward.amount -= float(order.total_price)
                    order.paid = True
                    existing_reward.save()
                else:  # -------- payment type not reward -> increment reward  points
                    if payment_type == VALID_PAYMENT_TYPES[1][0]:  # if Hesab Pay
                        """
                            this part handles import online payment
                            after succesfull payment, user is redirected to app and request is made 
                            to this endpoint. Here we transfer vendor's share to his account.
                        """
                        
                        status = r.get(get_order_payment_key(order_id))
                        # payment already in process
                        if status or order.paid:
                            logger.warning(f"online payment attempt on already paid order: {order_id}")
                            return Response()
                        acquire_payment_lock(order_id)
                        transaction_id = data.get("transaction_id", None)
                        if not transaction_id:
                            logger.info(f"transaction id not provided for order {order.id} online payment")
                            return Response(status=rsp_status.HTTP_400_BAD_REQUEST)
                        order.transaction_id = transaction_id
                        order.is_epay = True
                        order.paid = True
                        logger.info(f"order {order.id} paid online with transaction id {transaction_id}")
                        vendor_hesab_pay_account_number = self.get_vendor_account_number(order.vendor)
                        vendors = [
                            {
                                "account_number": vendor_hesab_pay_account_number,
                                "amount": int(int(order.total_price) - (int(order.total_price) * PLATFORM_ONLINE_PAYMENT_SHARE)),  # delivery + items price
                            }
                        ]
                        logger.info(f"initiating multi vendor payment for order {order.id}")
                        # any error in reward is not important, multi-vendor payment necessary
                        try:
                            self.handle_reward_increment(order, existing_reward)
                        except Exception as e:
                            pass
                        try:
                            # check redis
                            create_multi_vendor_payment(vendors,order)
                        except Exception as e:
                            logger.exception(f"multi vendor payment failed for order {order.id}: {e}")
                            
                            pass
                # ------------- either payment type, this general part should be done
                self.request.user.cart.clear()
                order.payment_type = payment_type
                order.status = ORDER_STATUS_CHOICES[2][1]  # preparing/execution
                order.save()

            event_data = {
                "accepted": True,
                "payment_type": payment_type,
                "order_id": order_id,
            }
            # ------------------ sendig order updates to vendor
            r.publish(
                f"pub:order:{order.id}",
                json.dumps(
                    {
                        "type": "ORDER_UPDATE",
                        "data": event_data,
                    }
                ),
            )
            self.send_notification(order)
            return Response()
        except Order.DoesNotExist:
            return Response(status=rsp_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"error in ar-order: {e}")
            return Response(status=rsp_status.HTTP_501_NOT_IMPLEMENTED)

    def handle_reward_increment(self, order, existing_reward):
        """handles reward increment logic"""
        if existing_reward:
            existing_reward.amount += round(
                (order.vendor.reward_percentage * float(order.total_price)) / 100
            )
            existing_reward.save()
        else:
            # ------  if buyer has no reward object of this vendor -> create new one
            if order.vendor.reward_percentage > 0:
                reward_to_add = round(
                    (order.vendor.reward_percentage * float(order.total_price)) / 100
                )
                Reward.objects.create(
                    vendor=order.vendor,
                    user=self.request.user,
                    amount=reward_to_add,
                )

    def send_notification(self, order):
        """creates notification for vendor when order is accepted by buyer"""
        activate_language(order.vendor.user_profile.pf_lang)
        notf = Notification.objects.create(
            title=_("order finalized by buyer!"),
            type="ORDER_ACCEPTED",
            data={},
            description=_("Order has been accepted by the buyer."),
            receiver=order.vendor.user,
            target_id=order.id,
        )
        deactivate_language()
        # ------------- sending notification to vendor
        push_notification.delay(order.vendor.user.id, notf.title, body=notf.description,data={"order_id": order.id})

    def get_vendor_account_number(self,vendor):
        """returns vendor hesab pay account number"""
        if vendor.hesabpay_number:
            return vendor.hesabpay_number
        return "0000000000000000"  # default account number


class OnlinePaymentView(views.APIView):
    """
    this is the first view the customer hits to start online payment
    this view takes order id and returns a session url for online payment
    app should open this session url in browser
    """

    permission_classes = [permissions.IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            order_id = data.get("order_id", None)
            if not order_id:
                return Response(status=rsp_status.HTTP_400_BAD_REQUEST)
            order = Order.objects.filter(id=order_id, is_epay=False).first()
            if order:
                logger.info(f"starting online payment session for user {request.user.id} order {order.id}")  
                items = order.items.all()
                items_ser = OrderItemSerializerLessDetail(items, many=True)
                data = items_ser.data.copy()
                data.append(
                    {
                        "id":1,
                        "name": "Delivery Cost",
                        "price": int(order.delivery_cost),
                    }
                )
                session_url = start_payment_session(data, order_id)
                return Response({"session_url": session_url["url"]})
            return Response(status=rsp_status.HTTP_400_BAD_REQUEST)
        except Order.DoesNotExist:
            return Response(status=rsp_status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.exception(f"error in online payment view: {e}")
            return Response(status=rsp_status.HTTP_501_NOT_IMPLEMENTED)


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
            # --------------- handling max tries
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
                r.expire(order_delivery_tries_key, ORDER_DELIVERY_ATTEMPTS_DELAY)
                if tries > MAX_ORDER_DELIVERY_TRIES_COUNT:
                    logger.warning("max order delivery attempts reached for order {}.".format(order_id))
                if not otp:
                    logger.warning("invalid otp provided for setting order {} delivered.".format(order_id))
                if otp and otp.is_expired(expire=ORDER_DELIVERY_OTP_EXPIRATION):
                    logger.warning("expired otp provided for setting order {} delivered.".format(order_id)) 
                    
                return Response(
                    {"detail": "otp_invalid_or_expired"},
                    status=rsp_status.HTTP_403_FORBIDDEN,
                )

            with atomic():
                # -------- setting order state Delivered state and carrier free
                order.status = ORDER_STATUS_CHOICES[4][1]  # delivered
                order.carrier.status = CARRIER_STATUS_CHOICES[0][0]  # free
                order.carrier.save()
                order.paid = True
                otp.delete()
                order.save()
                # ------------- deleting order delivery tries key------
                r.delete(order_delivery_tries_key)
                # ---------------- updating vendor's carriers in redis
                vendor = order.vendor
                vendor_carriers_key = get_vendor_carriers_key(vendor.id)
                b_c_c = r.hget(vendor_carriers_key, "b_c_c")  # busy carriers count
                b_c_c = int(b_c_c) - 1  # decrementing busy carrier's count
                r.hset(vendor_carriers_key, "b_c_c", b_c_c)
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
            deactivate_language
            # notificaiton for vendor + send by websocket
            activate_language(vendor.user_profile.pf_lang)
            Notification.objects.create(
                title=_("Order Delivered"),
                description=_(f"Order {order_id} delivered successfully."),
                type="ORDER_DELIVERED",
                receiver=order.vendor.user,
                data={"order_id": order_id},
                target_id=order.id,
            )
            push_notification.delay(
                order.vendor.user.id,
                _("Order Delivered"),
                body=_(f"Order {order_id} delivered successfully."),
                data={"order_id": order_id},
            )
            deactivate_language()
            ser = COrderSerializer(order)
            return Response(
                ser.data,
                status=rsp_status.HTTP_202_ACCEPTED,
            )
        except Order.DoesNotExist:
            return Response({"detail": "no_macthing_order"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"detail": "invalid_otp"}, status=400)
        except PermissionDenied:
            return Response(
                {"detail": "not_allowed"},
                status=rsp_status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            logger.exception(f"error in set order as delivered: {e}")
            return Response(
                {"detail": "uknown error occured"},
                status=rsp_status.HTTP_501_NOT_IMPLEMENTED,
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
                        price=item.food.min_price,
                        quantity=item.quantity,
                    )
                return Response()
            except Exception as e:
                logger.exception(f"error in re-order: {e}")
                pass
            return Response(status=rsp_status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(
            {"detail": "provide_order_id"}, status=rsp_status.HTTP_400_BAD_REQUEST
        )


class RedirectPaymentSuccess(views.APIView):
    """
    this endpoint is called by hesab pay after payment is successful
    it redirects the request to customer app with transaction_id
    """
    permission_classes = [AllowAny]
    def get(self, *args, **kwargs):
        try:
            params_data = self.request.query_params.get("data", None)
            data_dict = json.loads(params_data)
            if data_dict.get("success") != True:
                return Response(status=rsp_status.HTTP_400_BAD_REQUEST)
            transaction_id = data_dict.get("transaction_id", None)
            if transaction_id is None:
                return Response(status=rsp_status.HTTP_400_BAD_REQUEST)
            app_link = f"zaytonfood://hesabpay/success?transaction_id={transaction_id}"
            response = Response(status=rsp_status.HTTP_302_FOUND)
            response["Location"] = app_link
            return response
        except Exception as e:
            logger.exception(f"error in redirect payment success view: {e}")
            return Response(status=rsp_status.HTTP_500_INTERNAL_SERVER_ERROR)


class RedirectPaymentFailure(views.APIView):
    """
    this endpoint is called by hesab pay after payment is failed
    this view redirects success url to mobile app and sends session id.
    """
    permission_classes = [AllowAny]

    def get(self, *args, **kwargs):
        try:
            params_data = self.request.query_params
            data_dict = json.loads(params_data)
            message = data_dict.get("message", None)
            if not message:
                message = "impossible_to_process_payment"
            app_link = f"zaytonfood://hesabpay/failure?reason={message}"
            response = Response(status=rsp_status.HTTP_302_FOUND)
            response["Location"] = app_link
            return response
        except Exception as e:
            return Response(status=rsp_status.HTTP_500_INTERNAL_SERVER_ERROR)
