import json
from zoneinfo import ZoneInfo
from django.conf import settings
from marketplace.models import Discount, Food
from api.permissions import IsVendor, IsVendorOfDiscount, IsVendorOfOrder
from order.serializers import VOrderSerializer
from order.models import ORDER_STATUS_CHOICES, Order
from multiVend.settings.base import PUBLIC_PLATFORM_ITEM_COMMISSION_FEE
from accounts.models import (
    ADMIN,
    CARRIER,
    CARRIER_ADD_OTP_EXPIRATION,
    CUSTOMER,
    REST,
    User,
    UserOtp,
)
from carrier.models import CARRIER_STATUS_CHOICES, Carrier
from carrier.serializers import CarrierSerializer
from accounts.utils import OTP_VERIFY_CARRIER, generate_otp, send_otp
from marketplace.utils import estimate_travel_time_graphhopper, haversine_distance
from cart.models import Cart
from live.models import Notification
from live.serializers import NotificationSerializer
from carrier.utils import get_carrier_key
from vendor.models import OpeningHour
from .serializers import (
    DiscountSerializer,
    OpeningHourSerializer,
    VendorSerializerDetailed,
)
from marketplace.backends import FoodFilterSet, VOrderFilterSet
from marketplace.serializers import FoodSerializerDetail
from api.permissions import IsVendorApproved, IsVendorOfFood
from rest_framework import permissions, viewsets, views, status, filters
from rest_framework.response import Response
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone as tz
from dateutil.parser import parser as date_parser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone as dj_tz

from rest_framework.exceptions import NotAcceptable
from api.permissions import IsVendorOfCarrier
from rest_framework import parsers, serializers
from .utils import get_vendor_carriers_key, r
from django.utils.translation import activate, deactivate, gettext as _
from rest_framework.decorators import action


# Create your views here.


"""Vendor API Views"""


class VendorAPIView(views.APIView):
    """
    This view enables a vendor to see, edit and delete its vendor account.
    """

    permission_classes = [permissions.IsAuthenticated, IsVendor]
    http_method_names = ["get", "patch", "delete"]

    def get(self, *args, **kwargs):
        """returns vendor details"""
        vendor = self.request.user.vendor
        serializer = VendorSerializerDetailed(vendor)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, *args, **kwargs):
        """enables vendor and related userprofile update"""
        data = self.request.data
        vendor = self.request.user.vendor
        vendor_serializer = VendorSerializerDetailed(vendor, data=data, partial=True)
        vendor_serializer.is_valid(raise_exception=True)
        vendor_serializer.save()
        # success
        return Response(vendor_serializer.data, status=status.HTTP_200_OK)

    def delete(self, *args, **kwargs):
        """overriden to cancel vendor account"""
        user = self.request.user
        vendor = user.vendor
        vendor.delete()
        user.delete()
        return Response(status=status.HTTP_200_OK)


class ConvertToVendorAPIView(views.APIView):
    http_method_names = ["post"]

    def post(self, *args, **kwargs):
        """
        THis method converts a user to a vendor account
        body: vendor_name
        """
        # if user is already a vendor
        user = self.request.user
        if user.role in (REST, CARRIER, ADMIN):
            return Response(
                {"error": "user is not allowed to convert to vendor"},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = self.request.data
        ser = VendorSerializerDetailed(data=data, context={"request": self.request})
        ser.is_valid(raise_exception=True)
        vendor = ser.save()
        user.cart.delete()
        # setting vendor's carriers in redis
        vendor_carriers_key = get_vendor_carriers_key(vendor.id)
        r.hset(vendor_carriers_key, mapping={"f_c_c": 0, "b_c_c": 0, "total_c_c": 0})
        return Response(ser.data, status=status.HTTP_201_CREATED)


class VendorFoodsManageViewSet(viewsets.ModelViewSet):
    """this class enables CRUD operations on foods of a vendor"""

    serializer_class = FoodSerializerDetail
    permission_classes = [permissions.IsAuthenticated, IsVendorOfFood, IsVendorApproved]
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["-created_at"]
    # filering
    filterset_class = FoodFilterSet
    # searching
    search_fields = ["name", "category__name", "description"]

    def get_queryset(self):
        """any queryset should be of the requesting vendor"""
        query_set = Food.objects.filter(vendor__user__id=self.request.user.id)
        return query_set

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["vendor"] = self.request.user.vendor.id
        return context


class ManageDiscountViewSet(viewsets.ModelViewSet):
    serializer_class = DiscountSerializer
    # permission_classes = [permissions.IsAuthenticated, IsVendorOfDiscount]

    def get_queryset(self):
        return Discount.objects.filter(vendor=self.request.user.vendor)

    def create(self, request, *args, **kwargs):
        data = request.data
        ids = data.get("ids", None)
        if not ids:
            return Response(
                {"detail": "no_foods_selected"}, status=status.HTTP_400_BAD_REQUEST
            )
        data["vendor"] = self.request.user.vendor.id
        ser = DiscountSerializer(data=data)
        ser.is_valid(raise_exception=True)
        # preventing duplicate
        if Discount.objects.filter(amount=data["amount"]).exists():
            return Response(
                {"detail": "already_exists"}, status=status.HTTP_409_CONFLICT
            )
        foods = Food.objects.filter(id__in=ids).select_related(
            "vendor__user", "discount"
        )
        # rejecting discount on other vendor's fooditems, and already-having items
        for food in foods:
            if food.vendor.user != self.request.user:
                return Response(
                    {"detail": "you_are_not_allowed"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if food.discount != None and food.discount.is_active:
                return Response(
                    {"detail": "fooditems_have_already_discount"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        discount = ser.save()
        Food.objects.filter(id__in=ids).update(discount=discount)
        return Response(ser.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """updating a discount object"""
        data = request.data
        new_ids = data.get("ids", None)
        pre_ids = data.get("pre_ids", None)
        if not (new_ids and pre_ids):
            return Response(
                {"detail": "no_foods_selected"}, status=status.HTTP_400_BAD_REQUEST
            )
        # -------  doing set operations and imporve performance
        new_ids = set(new_ids)
        pre_ids = set(pre_ids)
        # new foods are those not in previous ids, but in new ids
        new_foods_to_set_discount = set.difference(new_ids, pre_ids)
        # removing-discount are those not in new ids
        pre_foods_to_remove_discount = set.difference(pre_ids, new_ids)
        instance = self.get_object()
        # ------- -- updating the discount object
        ser = DiscountSerializer(instance, data=data, partial=True)
        ser.is_valid(raise_exception=True)
        instance = ser.save()
        # removing discounts from previous food items
        Food.objects.filter(id__in=pre_foods_to_remove_discount).update(discount=None)
        # adding discount on new foods
        Food.objects.filter(id__in=new_foods_to_set_discount).update(discount=instance)
        return Response(ser.data, status=status.HTTP_200_OK)


class ManageOpeningHours(viewsets.ModelViewSet):
    serializer_class = OpeningHourSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def get_queryset(self):
        return OpeningHour.objects.filter(vendors__in=[self.request.user.vendor])

    def perform_create(self, serializer):
        data = serializer.validated_data
        weekday = data.get("weekday", None)
        start_hour = data.get("start_hour", None)
        end_hour = data.get("end_hour", None)
        is_holiday = data.get("is_holiday", None)

        qs = self.get_queryset()
        # preventing repetition
        if weekday and qs.filter(weekday=weekday):
            raise NotAcceptable(detail="already_exists", code=403)
        if not is_holiday and (not start_hour or not end_hour):
            raise NotAcceptable(detail="no_hours_mentioned", code=403)
        if start_hour and end_hour:
            if start_hour > end_hour:
                raise NotAcceptable(detail="incorrect_hour_set", code=403)

        instance = serializer.save()
        vendor = self.request.user.vendor
        vendor.opening_hours.add(instance)
        return instance

    def perform_update(self, serializer):
        data = serializer.validated_data
        weekday = data.get("weekday", None)
        start_hour = data.get("start_hour", None)
        end_hour = data.get("end_hour", None)
        is_holiday = data.get("is_holiday", None)

        qs = self.get_queryset().exclude(id=serializer.instance.id)
        # preventing repetition
        if weekday and qs.filter(weekday=weekday):
            raise NotAcceptable(detail="already_exists", code=403)
        if not is_holiday and (not start_hour or not end_hour):
            raise NotAcceptable(detail="no_hours_mentioned", code=403)
        if start_hour and end_hour:
            if start_hour > end_hour:
                raise NotAcceptable(detail="incorrect_hour_set", code=403)

        return serializer.save()


class AddCarrierAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    http_method_names = ["post", "patch"]

    def post(self, *args, **kwargs):
        """this method verifies the phone_number entered and sends OTP"""
        data = self.request.data
        phone_number = data.get("phone_number")
        account = User.objects.filter(phone_number=phone_number).first()
        if not account or not account.is_active:
            raise serializers.ValidationError(
                {"detail": "no_account_found_by_that_email"}
            )
        if account.role in (REST, ADMIN) or account.is_admin or account.is_superadmin:
            raise NotAcceptable(detail="You are not allowed", code=403)
        elif account.role == CARRIER:
            raise serializers.ValidationError({"detail": "already_exists"})

        # sending otp
        send_otp(
            account,
            phone_number,
            OTP_VERIFY_CARRIER,
            vendor_name=self.request.user.vendor.vendor_name,
        )
        return Response({"message": "otp_sent"}, status=status.HTTP_200_OK)

    def patch(self, *args, **kwargs):
        """verifies the otp and converts the phone_number-account to carrier account"""
        data = self.request.data
        phone_number = data.get("phone_number")
        otp = data.get("otp")
        try:
            otp = UserOtp.objects.get(otp=otp)
            if otp.is_expired(CARRIER_ADD_OTP_EXPIRATION):
                return Response(
                    {"detail": "otp_expired"}, status=status.HTTP_400_BAD_REQUEST
                )
            if not otp.user.phone_number == phone_number:
                return Response(
                    {"detail": "no_matching_otp"}, status=status.HTTP_400_BAD_REQUEST
                )
            carrier_user_account = otp.user
            profile = carrier_user_account.profile
            vendor = self.request.user.vendor
            carrier = Carrier.objects.create(
                user=carrier_user_account, user_profile=profile, vendor=vendor
            )
            carrier_user_account.role = CARRIER
            otp.delete()
            carrier_user_account.cart.delete()
            carrier_user_account.save()
            # increasing carrier's count for vendor
            vendor_carriers_key = get_vendor_carriers_key(vendor.id)
            f_c_c = json.loads(r.hget(vendor_carriers_key, "f_c_c"))
            total_c_c = json.loads(r.hget(vendor_carriers_key, "total_c_c"))
            if not f_c_c:
                f_c_c = 0
            f_c_c = int(f_c_c) + 1
            total_c_c = int(total_c_c) + 1
            r.hset(vendor_carriers_key, "f_c_c", f_c_c)
            r.hset(vendor_carriers_key, "total_c_c", total_c_c)
            # setting carrier live status in redis
            carrier_key = get_carrier_key(carrier.id)
            vendor_location = self.request.user.profile.location
            vendor_location = (vendor_location.y, vendor_location.x)
            r.set(
                carrier_key,
                json.dumps(
                    {
                        "return_estimate": 0,
                        "location": vendor_location,
                        "destination": vendor_location,
                    }
                ),
            )

            return Response(status=status.HTTP_201_CREATED)

        except UserOtp.DoesNotExist:
            return Response(
                {"error": "no_matching_otp"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print("error", e)
            return Response(
                {"error": "UKNOWN_ERROR"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ManageCarrierViewSet(viewsets.ModelViewSet):
    """
    This view is only accessible by a vendor to manage carriers
    GET, PATCH, DELETE
    UPDATEable: is_active, id_document
    """

    permission_classes = [permissions.IsAuthenticated, IsVendor, IsVendorOfCarrier]
    serializer_class = CarrierSerializer
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]
    http_method_names = ["delete", "get", "patch"]

    def get_queryset(self):
        """only this vendor carriers be listed"""
        queryset = Carrier.objects.filter(vendor=self.request.user.vendor)
        return queryset

    def get_serializer_context(self):
        context = super(ManageCarrierViewSet, self).get_serializer_context()
        context["vendor"] = self.request.user.vendor.id
        return context

    def perform_destroy(self, instance):
        """converting to a normal user"""
        user = instance.user
        instance.delete()
        user.role = CUSTOMER
        Cart.objects.create(user=user)
        vendor = self.request.user.vendor
        # decreasing carrier's count
        vendor_carriers_key = get_vendor_carriers_key(vendor.id)
        total_c_c = json.loads(r.hget(vendor_carriers_key, "total_c_c"))
        total_c_c = int(total_c_c) - 1
        f_c_c = json.loads(r.hget(vendor_carriers_key, "f_c_c"))
        f_c_c = int(f_c_c) - 1
        r.hset(vendor_carriers_key, "total_c_c", total_c_c)
        r.hset(vendor_carriers_key, "f_c_c", f_c_c)
        user.save()



class CarriersNow(views.APIView):
    """this view returns list of vendor carriers sorted by
    nearst to farthest ones from vendor location"""

    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def get(self, *args, **kwargs):
        carriers = Carrier.objects.filter(
            vendor__id=self.request.user.vendor.id, is_active=True
        )
        live_vendor_carriers = []  # final list being returned
        for carrier in carriers:
            try:
                carrier_key = get_carrier_key(carrier.id)
                carrier_live_data = json.loads(r.get(carrier_key))
                carrier_current_location = carrier_live_data["location"]
                vendor_location = self.request.user.profile.location
                vendor_location = (vendor_location.y, vendor_location.x)
                time = 0
                if carrier.status == CARRIER_STATUS_CHOICES[0][0]:  # if carrier is free
                    distance_m = (
                        haversine_distance(*vendor_location, *carrier_current_location)
                        * 1000
                    )  # rough estimate, no maps used, meters
                    if distance_m > 200:  # if carrier is far from the resturant
                        time = estimate_travel_time_graphhopper(
                            carrier_current_location, vendor_location
                        )
                else:  # carrier is busy and has not reached to customer yet
                    customer_location = carrier_live_data["destination"]
                    time = estimate_travel_time_graphhopper(
                        carrier_current_location, customer_location
                    )
                details = {"name": carrier.name, "return_time": time}
                live_vendor_carriers.append(details)
            except Exception as e:
                print("error occured while fetching live carrier status", e, e.args)
                details = {"name": carrier.name, "return_time": 0}
                live_vendor_carriers.append(details)

        live_vendor_carriers.sort(
            key=lambda x: int(x["return_time"])
        )  # sorting by nearst to longest carriers
        return Response({"carriers": live_vendor_carriers}, status=status.HTTP_200_OK)


class VendorRevenueView(views.APIView):
    """THis view returns vendor revenue from different aspects"""

    permission_classes = [IsVendor, permissions.IsAuthenticated]

    def get(self, *args, **kwargs):
        """this method returns monthly, weekly and today's revenue"""
        vendor = self.request.user.vendor
        orders = Order.objects.filter(status="delivered", vendor=vendor)
        one_month_ago = tz.now() - tz.timedelta(days=30)
        one_week_ago = tz.now() - tz.timedelta(days=7)
        # --------------- this month revenue
        month_orders = orders.filter(created_at__gte=one_month_ago)
        monthly_revenue = month_orders.annotate(
            vendor_revenue=ExpressionWrapper(
                F("total_price")
                - F("total_items") * PUBLIC_PLATFORM_ITEM_COMMISSION_FEE,
                output_field=DecimalField(),
            )
        ).aggregate(total=Sum("vendor_revenue"))

        # ---------------- this week revenue
        week_orders = orders.filter(created_at__gte=one_week_ago)
        weekly_revenue = week_orders.annotate(
            vendor_revenue=ExpressionWrapper(
                F("total_price")
                - F("total_items") * PUBLIC_PLATFORM_ITEM_COMMISSION_FEE,
                output_field=DecimalField(),
            )
        ).aggregate(total=Sum("vendor_revenue"))

        # ---------------- today revenue
        today_orders = orders.filter(created_at__date=tz.now().date())
        totay_revenue = today_orders.annotate(
            vendor_revenue=ExpressionWrapper(
                F("total_price")
                - F("total_items") * PUBLIC_PLATFORM_ITEM_COMMISSION_FEE,
                output_field=DecimalField(),
            )
        ).aggregate(total=Sum("vendor_revenue"))

        return Response(
            {
                "monthly_revenue": monthly_revenue["total"] or 0,
                "weekly_revenue": weekly_revenue["total"] or 0,
                "today_revenue": totay_revenue["total"] or 0,
            }
        )

    def post(self, *args, **kwargs):
        """
        This method returns vendor revenue in custom range
        date format:
            "YYYY-MM-DDTHH:MM:SSZ" --- utc
             //     //  /   //  +4:30 AF
        """
        data = self.request.data
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if not start_date or not end_date:
            return Response(
                {"detail": "please provide start date and end date in AD"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        parser = date_parser()
        start_date = parser.parse(start_date)
        end_date = parser.parse(end_date)
        if tz.is_naive(start_date):
            start_date = tz.make_aware(date_parser(start_date))  #
        if tz.is_naive(start_date):
            end_date = tz.make_aware(date_parser(end_date))

        vendor = self.request.user.vendor
        orders = Order.objects.filter(
            vendor=vendor,
            status="delivered",
            created_at__gte=start_date,
            created_at__lte=end_date,
        )
        total_revenue = orders.annotate(
            vendor_earning=ExpressionWrapper(
                F("total_price")
                - F("total_items") * PUBLIC_PLATFORM_ITEM_COMMISSION_FEE,
                output_field=DecimalField(),
            )
        ).aggregate(total=Sum("vendor_earning"))

        return Response({"total-revenue": total_revenue["total"]})


class ListVendorOrders(viewsets.ReadOnlyModelViewSet):
    """This enables a vendor to see past orders it completed successfully."""

    serializer_class = VOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOfOrder]
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]

    ordering_fields = ["total_price", "created_at"]
    ordering = ["-created_at"]
    # filering
    filterset_class = VOrderFilterSet

    def get_queryset(self):
        queryset = Order.objects.filter(vendor=self.request.user.vendor)
        return queryset


class AcceptRejectOrderView(views.APIView):
    """
    THis view enables a vendor either accept or reject the new order. It adjusts order status appropriately.
    """

    permission_classes = [permissions.IsAuthenticated, IsVendorOfOrder]

    def post(self, *args, **kwargs):
        data = self.request.data
        order_id = data["order_id"]
        accepted = data["accepted"]

        try:
            order = Order.objects.get(id=order_id)
            # check if this vendor owns the order
            self.check_object_permissions(self.request, order)
            # only 'waiting' order can be set to preparing
            if not order.status == ORDER_STATUS_CHOICES[1][1]:
                return Response(
                    {"detail", "order_not_waiting_state"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            # accepted
            profile = order.user.profile
            activate(profile.pf_lang)
            notf = Notification(receiver=order.user)
            if accepted == True:
                # order accepted -> set as preparing, send notification
                order.status = ORDER_STATUS_CHOICES[2][1]  # preparing/execution
                order.save()
                notf.title = _("Your order has been accepted.")
                notf.type = "ORDER_ACCEPTED"
                notf.save()
                deactivate()
                # creating OTP
                r.publish(
                    f"pub:user:{order.user.id}",
                    json.dumps(
                        {
                            "type": "ORDER_ACCEPTED",
                            "data": NotificationSerializer(notf).data,
                        }
                    ),
                )
                return Response(
                    {"message": "order_accepted"}, status=status.HTTP_200_OK
                )
            # order rejected -> delete order, send notification
            order.cancel_order()
            notf.title = _("We are sorry! Your order has been rejected.")
            notf.type = "order_rejected"
            notf.save()
            r.publish(
                f"pub:user:{order.user.id}",
                json.dumps(
                    {
                        "type": "ORDER_REJECTED",
                        "data": NotificationSerializer(notf).data,
                    }
                ),
            )

            # sending notification to customer ....
            return Response({"message": "order_rejected"}, status=status.HTTP_200_OK)

        except Order.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print("error:", e.args, e)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class CalculateOrderTimeAndDeliveryCost(views.APIView):
    """
    This view takes new order id and estimates new order reaching-time considering
    preparing orders count, free carriers count and total carriers count of vendor
    returns {"estimated":integer}
    """

    permission_classes = [permissions.IsAuthenticated, IsVendorOfOrder]

    def get(self, *args, **kwargs):
        # ------------------ estimating only this order distance and reach time
        request_data = self.request.query_params
        new_order_id = request_data.get("order_id", None)
        if not new_order_id:
            return Response(
                {"detail": "provide_new_order_id"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            order = Order.objects.get(id=int(new_order_id))
            # check if the vendor owns this order
            self.check_object_permissions(self.request, order)
            # ------------------ estimateing travel time for new order
            vendor = self.request.user.vendor
            user_location = order.user.profile.location
            user_location = (user_location.y, user_location.x)  # as lat,lon
            vendor_location = vendor.user_profile.location
            vendor_location = (vendor_location.y, vendor_location.x)  # lat,lon
            estimated, distance_km = estimate_travel_time_graphhopper(
                vendor_location, user_location
            )

            # ----------------- getting total free carriers and total preparing orders
            vendor_carriers_key = get_vendor_carriers_key(vendor.id)
            _3_hours_ago = tz.now() - tz.timedelta(hours=3)
            preparing_orders_count = Order.objects.filter(
                vendor=vendor,
                status=ORDER_STATUS_CHOICES[2][0],  # preparing
                created_at__gte=_3_hours_ago,
            ).count()

            free_carriers_count = r.hget(vendor_carriers_key, "f_c_c")
            total_carriers_count = r.hget(vendor_carriers_key, "total_c_c")
            print(
                "free carriers--",
                free_carriers_count,
                "\ntotal carriers---",
                total_carriers_count,
                "estiated before conditions",
                estimated,
                "\npreparing_orders_count",
                preparing_orders_count,
            )
            if free_carriers_count:
                free_carriers_count = int(json.loads(free_carriers_count))
            else:
                free_carriers_count = vendor.carriers.count()
                r.hset(vendor_carriers_key, "f_c_c", free_carriers_count)

            if total_carriers_count:
                total_carriers_count = int(json.loads(total_carriers_count))
            else:
                total_carriers_count = vendor.carriers.count()
                r.hset(vendor_carriers_key, "total_c_c", total_carriers_count)
            total_time = estimated
            print("estimated....", estimated, total_carriers_count, free_carriers_count)
            # ----------------- applying conditions and finalizing estimation of time  ...
            if preparing_orders_count <= total_carriers_count:
                print("in first condition")
                if preparing_orders_count < free_carriers_count:
                    total_time = estimated
                elif preparing_orders_count >= free_carriers_count:
                    print("preparing greater than free count")
                    total_time = estimated + 20
            elif preparing_orders_count > total_carriers_count:
                print("in second condition")
                if free_carriers_count == 0:
                    total_time = (
                        estimated
                        + (20 * round(preparing_orders_count / total_carriers_count))
                        + 10
                    )
                else:
                    total_time = estimated + (
                        20 * round(preparing_orders_count / total_carriers_count)
                    )
            # ------------------ calculating delivery fee ----------------/---------------------
            delivery_cost = None
            v_mfdd = vendor.mfdd  # vendor's maximum free distance delivery
            v_mfcfd = vendor.mfcfd  # vendor's minimum food count free delivery
            if (
                vendor.mfcfd
                and vendor.mfdd > 0
                and distance_km < v_mfdd
                and order.total_items > v_mfcfd
            ):
                delivery_cost = 0
            else:
                delivery_cost = 2 * (distance_km * vendor.delivery_fee_km)

            return Response({"estimated": total_time, "delivery_cost": delivery_cost})
        except Exception as e:
            print("error in order time calculation view\n", e, "\n", e.args)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)
