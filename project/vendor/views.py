from datetime import datetime
import time
import json
from marketplace.models import Discount, Food
from api.permissions import (
    IsOrderPreparingState,
    IsVendor,
    IsVendorOfObject,
    IsVendorOfObject,
)
from order.serializers import VOrderSerializer
from order.models import ORDER_STATUS_CHOICES, Order, OrderItem
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
from marketplace.utils import (
    StandardResultSetPagination,
    estimate_travel_time_graphhopper,
    haversine_distance,
)
from cart.models import Cart
from carrier.utils import get_carrier_key
from live.models import Notification
from live.utils import send_notification
from vendor.models import OpeningHour
from .serializers import (
    DiscountSerializer,
    OpeningHourSerializer,
    VendorSerializerDetailed,
)
from marketplace.backends import FoodFilterSet, VOrderFilterSet
from marketplace.serializers import VFoodSerializerDetail
from api.permissions import IsVendorApproved, IsVendorOfObject
from rest_framework import permissions, viewsets, views, status, filters
from rest_framework.response import Response
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Prefetch
from django.utils import timezone as tz
from django.db.transaction import atomic
from django.contrib.gis.geos import Point

from dateutil.parser import parser as date_parser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import NotAcceptable
from api.permissions import IsVendorOfObject
from rest_framework import parsers, serializers
from .utils import get_vendor_carriers_key, r, revert_discount, apply_discount
from django.utils.translation import gettext as _
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from django.utils.translation import deactivate as deactivate_language
from django.utils.translation import activate as activate_language
from live.utils import send_notification

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
        print("data came to vendor update view", data)
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
                {"detail": "not_allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = self.request.data
        print("data came in covert-to-vendor", data)
        ser = VendorSerializerDetailed(data=data, context={"request": self.request})
        # try:
        ser.is_valid(raise_exception=True)
        # except Exception as e:
        # print("eroroororo", e)
        print("no eroor in covernt to endor", data)

        with atomic():
            try:
                vendor = ser.save()
                user.cart.delete()
                # setting vendor's carriers in redis
                vendor_carriers_key = get_vendor_carriers_key(vendor.id)
                r.hset(
                    vendor_carriers_key,
                    mapping={"f_c_c": 0, "b_c_c": 0, "total_c_c": 0},
                )
            except:
                print("error in convert-to-vendor")
                raise Exception()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class VendorFoodsManageViewSet(viewsets.ModelViewSet):
    """this class enables CRUD operations on foods of a vendor"""

    serializer_class = VFoodSerializerDetail
    permission_classes = [
        permissions.IsAuthenticated,
        IsVendorOfObject,
        IsVendorApproved,
    ]
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
    permission_classes = [permissions.IsAuthenticated, IsVendorOfObject]

    def get_queryset(self):
        return Discount.objects.filter(vendor=self.request.user.vendor)

    def create(self, request, *args, **kwargs):
        """
        this creates a new discount
        the client side should provide ids[] of food items
        """
        data = request.data
        ids = data.get("ids", None)
        amount = data.get("amount", None)
        days_to_expire = data.get("days", None)
        vendor_id = request.user.vendor.id

        if not (ids and amount and days_to_expire):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        if not type(days_to_expire) == int:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        deadline = tz.now() + tz.timedelta(days=days_to_expire)
        data["deadline"] = deadline
        data["vendor"] = self.request.user.vendor.id
        ser = DiscountSerializer(data=data)
        ser.is_valid(raise_exception=True)
        # preventing duplicate
        if Discount.objects.filter(amount=amount).exists():
            return Response(
                {"detail": "discount_already_exists"}, status=status.HTTP_409_CONFLICT
            )

        foods = Food.objects.filter(id__in=ids, vendor__id=vendor_id).select_related(
            "vendor__user", "discount"
        )
        # rejecting discount on other vendors fooditems, and upserting

        with atomic():
            discount = ser.save()
            for food in foods:
                if food.discount != None:
                    # if food has already discount, reset to original price and set newset discount
                    revert_discount(food, food.discount.amount)
                # applying discount to all prices of food
                apply_discount(food, amount)
                food.discount = discount
            Food.objects.bulk_update(foods, ["discount", "min_price", "prices"])

        return Response(ser.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        """
        updating a discount object
        input: ids --> list of ids to apply discount
        * if amount of discount is set to an existing discount value, denied
        * if a food belongs to another discount, last one is set.
        * this view considers 3 scenarios:
            1- updating discount amount and updating food prices accordingly
            2- adding new foods to discount and updating prices accordingly
            3- removing discount from foods

        """
        data = request.data
        pre_discount = self.get_object()
        new_ids = data.get("ids", None)
        pre_ids = set(pre_discount.foods.values_list("pk", flat=True))
        vendor_id = request.user.vendor.id
        if not new_ids:
            return Response(
                {"detail": "no_foods_selected"}, status=status.HTTP_400_BAD_REQUEST
            )
        # updating new discount object
        pre_discount_amount = pre_discount.amount
        ser = DiscountSerializer(pre_discount, data=data, partial=True)
        ser.is_valid(raise_exception=True)
        new_discount_amount = ser.validated_data.get("amount", None)
        if (
            Discount.objects.filter(amount=new_discount_amount)
            .exclude(id=pre_discount.id)
            .exists()
        ):
            return Response(
                {"detail": "discount_already_exists_with_this_amount"},
                status=status.HTTP_409_CONFLICT,
            )
        # ----------- removing discounts from previous food items and finding new foods
        # set operations
        new_ids = set(new_ids)
        # new foods ids that are not in pre_ids
        ids_foods_to_add_discount = set.difference(new_ids, pre_ids)
        # pre foods ids that are not in new ids and discount should be removed
        ids_foods_to_remove_discount = set.difference(pre_ids, new_ids)
        # pre foods ids that need  discount update
        ids_foods_to_update_discount = set.intersection(new_ids, pre_ids)
        vendor_foods = Food.objects.filter(vendor__id=vendor_id)
        with atomic():
            # new discount
            new_discount = ser.save()
            # -------------  updating prices of foods having this discount already
            foods_to_update_discount = vendor_foods.filter(
                id__in=ids_foods_to_update_discount
            ).only("id", "min_price", "prices", "discount")
            for food in foods_to_update_discount:
                # reverting food prices to original ones
                revert_discount(food, pre_discount_amount)
                # applying discount to all prices of food
                apply_discount(food, new_discount_amount)
                food.discount = new_discount
            Food.objects.bulk_update(
                foods_to_update_discount, ["prices", "min_price", "discount"]
            )
            # --------------reseting prices and removing discount of removed foods from this discount
            foods_to_remove_discount = vendor_foods.filter(
                id__in=ids_foods_to_remove_discount
            ).only("id", "min_price", "prices", "discount")
            for food in foods_to_remove_discount:
                print("discount removed...", food.id)
                # reverting food prices to original ones
                revert_discount(food, pre_discount_amount)
                # applying discount to all prices of food
                food.discount = None
            Food.objects.bulk_update(
                foods_to_remove_discount, ["prices", "min_price", "discount"]
            )

            # ---------------- adding discount on new foods and updatin their price
            foods_to_add_discount = (
                vendor_foods.filter(id__in=ids_foods_to_add_discount)
                .select_related("discount")
                .only("id", "min_price", "prices", "discount")
            )
            for food in foods_to_add_discount:
                print("discount added...", food.id)
                # applying discount to all prices of food
                if food.discount != None:
                    revert_discount(food, food.discount.amount)
                apply_discount(food, new_discount_amount)
                food.discount = new_discount
            Food.objects.bulk_update(
                foods_to_add_discount, ["prices", "min_price", "discount"]
            )
        return Response(ser.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="edable")
    def enable_disable(self, request, *args, **kwargs):
        """
        this endpoint enables or disables a discount
        edable takes True and False, first one means enable latter means disable.
        if edable is None, no enable or disable happens.
        request must be sent out of update and exact.
        """
        typ = request.data.get("type", "enable")
        discount = self.get_object()
        try:
            foods = discount.foods.only("id", "min_price", "prices")
            # enable discount
            edable = None
            if typ == "enable" and discount.is_active == False:
                edable = True
                for food in foods:
                    apply_discount(food, discount.amount)
            # disable discount
            elif typ == "disable" and discount.is_active == True:
                edable = False
                for food in foods:
                    revert_discount(food, discount.amount)
            # bulk update
            with atomic():
                if edable in (True, False):
                    Food.objects.bulk_update(foods, ["min_price", "prices"])
                    discount.is_active = edable
                    discount.save()
                else:
                    print("no changes in discount...")
            return Response()

        except Exception as e:
            print("error in deactivate of discount", e)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

    def patch(self, *args, **kwargs):
        """this method verifies the phone_number and sends OTP, no carrier creation"""
        # ---- authorization and validation
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

        # ----- sending otp to user's phone number
        otp = generate_otp()
        send_otp.delay(
            otp=otp,
            user_id=account.id,
            phone_number=phone_number,
            typ=OTP_VERIFY_CARRIER,
            vendor_name=self.request.user.vendor.vendor_name,  # extra data
        )
        return Response({"message": "otp_sent"}, status=status.HTTP_200_OK)

    def post(self, *args, **kwargs):
        """verifies the otp and converts to carrier account"""
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
            # --------------- re-balancing carriers status of vendor
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
                {"detail": "no_matching_otp"}, status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print("error", e)
            return Response(
                {"detail": "UKNOWN_ERROR"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ManageCarrierViewSet(viewsets.ModelViewSet):
    """
    This view is only accessible by a vendor to manage carriers
    GET, PATCH, DELETE
    UPDATEable: is_active, id_document
    """

    permission_classes = [permissions.IsAuthenticated, IsVendor, IsVendorOfObject]
    serializer_class = CarrierSerializer
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]
    http_method_names = ["delete", "get", "patch"]

    def get_queryset(self):
        """only this vendor carriers be listed"""
        queryset = Carrier.objects.filter(vendor=self.request.user.vendor)
        return queryset

    def list(self, request, *args, **kwargs):
        """overriden to add total carriers and free carriers amount"""
        try:
            vendor_carriers_key = get_vendor_carriers_key(self.request.user.vendor.id)
            total_c_c = json.loads(r.hget(vendor_carriers_key, "total_c_c"))
            f_c_c = json.loads(r.hget(vendor_carriers_key, "f_c_c"))
            b_c_c = json.loads(r.hget(vendor_carriers_key, "b_c_c"))

            # serializing and sending response
            queryset = self.filter_queryset(self.get_queryset())
            ser = self.get_serializer(queryset, many=True)
            return Response(
                {
                    "total_carriers": total_c_c,
                    "free_carriers": f_c_c,
                    "busy_carriers": b_c_c,
                    "carriers": ser.data,
                }
            )
        except Exception as e:
            print("error in list carriers", e)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get_serializer_context(self):
        context = super(ManageCarrierViewSet, self).get_serializer_context()
        context["vendor"] = self.request.user.vendor.id
        return context

    def perform_destroy(self, instance):
        """converting a carrier to a normal user"""
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
    """
    this view returns list of vendor carriers sorted by
    nearst to farthest ones from vendor location
    it is used when assigning carriers for order delivery task
    """

    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def get(self, *args, **kwargs):
        carriers = Carrier.objects.filter(
            vendor__id=self.request.user.vendor.id, is_active=True
        ).only("id", "status", "name")
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
                        time = int(
                            estimate_travel_time_graphhopper(
                                carrier_current_location, vendor_location
                            )
                        )
                else:  # carrier is busy and has not reached to customer yet
                    customer_location = carrier_live_data["destination"]
                    time = int(
                        estimate_travel_time_graphhopper(
                            carrier_current_location, customer_location
                        )
                    )
                details = {"id": carrier.id, "name": carrier.name, "return_time": time}
                live_vendor_carriers.append(details)
            except Exception as e:
                print("error occured while fetching live carrier status", e, e.args)
                details = {
                    "id": carrier.id,
                    "name": carrier.name,
                    "return_time": 0,
                    "image": carrier.user_profile.picture,
                }
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

    pagination_class = StandardResultSetPagination
    serializer_class = VOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOfObject]
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
        """only vendor's order"""
        queryset = Order.objects.filter(vendor=self.request.user.vendor)
        return queryset

    @action(detail=False, methods=["get"], url_path="abstract")
    def abstract_orders_detail(self, request):
        queryset = self.get_queryset()
        today_orders = queryset.filter(created_at__date=tz.now().date())
        # mark vendor as active
        vendor = self.request.user.vendor
        vendor.is_available = True
        vendor.save()
        # details
        today_sale_amount = today_orders.filter(
            status=ORDER_STATUS_CHOICES[4][0]
        ).aggregate(total=Sum("total_price"))
        pending_orders_count = today_orders.filter(
            status=ORDER_STATUS_CHOICES[1][0]
        ).count()
        preparing_orders_count = today_orders.filter(
            status=ORDER_STATUS_CHOICES[2][0]
        ).count()
        carrying_orders_count = today_orders.filter(
            status=ORDER_STATUS_CHOICES[3][0]
        ).count()
        delivered_orders_count = today_orders.filter(
            status=ORDER_STATUS_CHOICES[4][0]
        ).count()
        return Response(
            {
                "total_sale": today_sale_amount["total"],
                "pending_orders": pending_orders_count,
                "preparing_orders": preparing_orders_count,
                "carryting_orders": carrying_orders_count,
                "delivered_orders": delivered_orders_count,
            }
        )


class CalculateOrderTimeAndDeliveryCost(views.APIView):
    """
    This view takes new order id and estimates new order reaching-time considering
    preparing orders count, free carriers count and total carriers count of vendor
    returns {"estimated":integer}
    """

    permission_classes = [permissions.IsAuthenticated, IsVendorOfObject]

    def get(self, *args, **kwargs):
        # ------------------ estimating only this order distance and reach time
        request_data = self.request.query_params
        new_order_id = request_data.get("order_id", None)
        accepted = request_data.get("is_accepted", None)
        if not new_order_id or not accepted:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            order = (
                Order.objects.filter(id=new_order_id)
                .prefetch_related(
                    Prefetch("items", queryset=OrderItem.objects.select_related("food"))
                )
                .first()
            )
            if order:
                # if vendor has rejected order, no calculation, just notify user
                if bool(accepted) == False:
                    order.cancel_order()
                    activate_language(self.request.user.profile.pf_lang)
                    notf = Notification.objects.create(
                        title=_("Order Rejected"),
                        description=_(
                            "sorry! your order has been rejected by restuarant!"
                        ),
                        type="VENDOR_REJECTED",
                        data={},
                        receiver=order.vendor.user,
                        target_id=order.id,
                    )
                    deactivate_language()
                    r.publish(
                        f"pub:order:{order.id}",
                        json.dumps(
                            {
                                "type": "VENDOR_REJECTED",
                                "data": {"orderId": order.id},
                            }
                        ),
                    )
                    send_notification.delay(
                        order.user.id,
                        notf.title,
                        body=notf.description,
                        data={"order_id": order.id},
                    )

                    return Response({"message": "order_order_rejected_by_vendor"})
                else:
                    # vendor accepted order
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
                                + (
                                    20
                                    * round(
                                        preparing_orders_count / total_carriers_count
                                    )
                                )
                                + 10
                            )
                        else:
                            total_time = estimated + (
                                20
                                * round(preparing_orders_count / total_carriers_count)
                            )
                    # ------------------- calculating preparation time
                    prep_time = 0
                    for item in order.items.all():
                        if item.food.is_ready_type:
                            today = tz.now().date()
                            # combine today's date with both times
                            ready_dt = datetime.combine(today, item.food.ready_time)
                            now_dt = datetime.combine(today, tz.now().time())
                            delta = ready_dt - now_dt
                            minutes = delta.total_seconds() / 60
                            if minutes > 0:
                                if prep_time < minutes:
                                    prep_time = minutes
                        else:
                            if prep_time < item.food.duration:
                                prep_time = item.food.duration
                    print(prep_time, "max preparation time")

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
                    # adding delivery cost to total price of order
                    order.delivery_cost = delivery_cost
                    total_cost = float(order.total_price) + float(order.delivery_cost)
                    total_time = round(float(prep_time) + float(estimated))
                    order.save()
                    return Response(
                        {
                            "estimation": round(total_time),
                            "delivery_cost": delivery_cost,
                            "preparation_time": round(prep_time),
                            "order_cost": round(order.total_price),
                            "total_cost": round(total_cost),
                            "order_id": order.id,
                            "total_time": total_time,
                        }
                    )
        except Exception as e:
            print("error in order time calculation view\n", e, "\n", e.args)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class SetOrderStateCarrying(views.APIView):
    """
    THis view enables a vendor(only) to choose an order and set it
    in carrying state. Besides, this view generates an OTP valid for 1 Day
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsVendorOfObject,
        IsOrderPreparingState,
    ]

    def post(self, *args, **kwargs):
        """vendor sets order status -carrying- and generates an OTP"""
        data = self.request.data
        order_id = data.get("order_id")
        carrier_id = data.get("carrier_id")
        try:
            order = Order.objects.get(id=order_id)
            carrier = Carrier.objects.get(pk=carrier_id)

            if (
                carrier.vendor != self.request.user.vendor
            ):  # vendor should own this carrier
                print("does not sdfjsdlfj")
                return Response(status=status.HTTP_403_FORBIDDEN)
            if carrier.status == CARRIER_STATUS_CHOICES[1][0]:  # carrerir busy
                return Response(
                    {"detail": "carrier_busy"}, status=status.HTTP_409_CONFLICT
                )
            #  vendor should own this order
            self.check_object_permissions(self.request, order)
            # if payment is online and not paid, not allowed
            # if order.is_credit:
            #     if not order.paid:
            #         return Response({"detail": "payment not completed"}, status=400)

            with atomic():
                # ----------------  making necessary things atomic
                order.carrier = carrier
                carrier.status = CARRIER_STATUS_CHOICES[1][0]  # busy
                UserOtp.objects.create(user=order.user, otp=order.otp)
                # setting order in carrying state
                order.status = ORDER_STATUS_CHOICES[3][1]  # carrying
                # order.otp = otp
                carrier.save()
                # setting carrier live status in redis
                order_user = order.user
                customer_location = order_user.profile.location
                customer_location = (customer_location.y, customer_location.x)
                order.destination = Point(
                    float(customer_location[1]), float(customer_location[0]), srid=4326
                )
                order.save()
                # estimation
                vendor = self.request.user.vendor
                vendor_location = vendor.user.profile.location
                vendor_location = (vendor_location.y, vendor_location.x)
                carrier_return_estimate = 2 * estimate_travel_time_graphhopper(
                    vendor_location, customer_location
                )
                carrier_key = get_carrier_key(carrier_id)
                r.set(
                    carrier_key,
                    json.dumps(
                        {
                            "return_estimate": carrier_return_estimate,
                            "location": vendor_location,
                            "destination": customer_location,
                        }
                    ),
                )
                # ---------------- updating vendor's carriers in redis
                vendor_carriers_key = get_vendor_carriers_key(vendor.id)
                b_c_c = r.hget(vendor_carriers_key, "b_c_c")
                if b_c_c:
                    b_c_c = json.loads(b_c_c)
                else:
                    b_c_c = 0
                    r.hset(vendor_carriers_key, "b_c_c", b_c_c)

                b_c_c = int(b_c_c) + 1  # increase it by one

                r.hset(
                    vendor_carriers_key, "b_c_c", b_c_c
                )  # updating busy carriers count
                f_c_c = json.loads(r.hget(vendor_carriers_key, "f_c_c"))
                f_c_c = int(f_c_c) - 1
                r.hset(vendor_carriers_key, "f_c_c", f_c_c)
                # ---------------------- creating notification for customer
                profile = order.user.profile

                activate_language(profile.pf_lang)
                notf = Notification.objects.create(
                    title=_("Order set as carrying"),
                    type="ORDER_SET_CARRYING",
                    receiver=order.user,
                    data={"order_id": order.id, "carrier_id": carrier_id},
                    target_id=order.id,
                    description=_("Your order is being carried, click to live track."),
                )
                deactivate_language()

                # -------------------- atomic end ----------------
                # ---------------------- sending notification to customer
                r.publish(
                    f"pub:user:{order.user.id}",
                    json.dumps(
                        {
                            "type": "ORDER_SET_CARRYING",
                            "data": {"order_id": order.id, "carrier_id": carrier_id},
                        }  # customer app should extract order id and subscribe it for live tracking
                    ),
                )
            send_notification.delay(
                order.user.id,
                notf.title,
                body=notf.description,
                data={"order_id": order.id},
            )

            print("notification sent to customer", f"pub:user:{order.user.id}")
            # --------------------- sending notification to carrier's room

            r.publish(
                f"pub:carrier:{carrier_id}",
                json.dumps(
                    {
                        "type": "ORDER_SET_CARRYING",
                        "data": {"order_id": order.id, "carrier_id": carrier_id},
                    }  # carrier app subscribes to order room either from notfications part or any and live tracking starts
                ),
            )
            # response
            return Response(
                {"message": "order_set_carrying"},
                status=status.HTTP_200_OK,
                # vendor app can/is subscribe to order room and track order live
            )

        except Order.DoesNotExist:
            return Response(
                {"detail": "no such order"}, status=status.HTTP_403_FORBIDDEN
            )
        except PermissionDenied as pd:
            print(pd, pd.args)
            return Response({"detail": "not_allowed"}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            print("error in set order as carrying", e)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
