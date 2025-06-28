import json
from django.conf import settings
from marketplace.models import Food
from api.permissions import IsVendor, IsVendorOfOrder
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
from accounts.utils import OTP_VERIFY_CARRIER, send_otp
from marketplace.utils import estimate_travel_time, haversine_distance
from vendor.models import OpeningHour
from .serializers import OpeningHourSerializer, VendorSerializerDetailed
from api.backends import FoodFilterSet, VOrderFilterSet
from marketplace.serializers import FoodSerializerDetail
from api.permissions import IsVendorApproved, IsVendorOfFood
from rest_framework import permissions, viewsets, views, status, filters
from rest_framework.response import Response
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone as tz
from dateutil.parser import parser as date_parser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import NotAcceptable
from api.permissions import IsVendorOfCarrier
from rest_framework import parsers, serializers
from .utils import r

# Create your views here.


"""Vendor API Views"""


class VendorAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    http_method_names = ["get", "patch", "delete"]

    def get(self, *args, **kwargs):
        """returns all vendor details"""
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
        if self.request.user.role in (REST, CARRIER, ADMIN):
            return Response(
                {"error": "user is not allowed to convert to vendor"},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = self.request.data
        ser = VendorSerializerDetailed(data=data, context={"request": self.request})
        ser.is_valid(raise_exception=True)
        ser.save()

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
        """this method verifies the email entered and sends OTP"""
        data = self.request.data
        email = data.get("email")
        account = User.objects.filter(email=email).first()
        if not account or not account.is_active:
            raise serializers.ValidationError(
                {"error": "no_account_found_by_that_email"}
            )
        if account.role in (REST, ADMIN) or account.is_admin or account.is_superadmin:
            raise NotAcceptable(detail="You are not allowed", code=403)
        elif account.role == CARRIER:
            raise serializers.ValidationError({"error": "already_exists"})

        # sending otp
        send_otp(
            self.request,
            account,
            OTP_VERIFY_CARRIER,
            vendor_name=self.request.user.vendor.vendor_name,
        )
        return Response({"message": "otp_sent"}, status=status.HTTP_200_OK)

    def patch(self, *args, **kwargs):
        """verifies the otp and converts the email-account to carrier account"""
        data = self.request.data
        email = data.get("email")
        otp = data.get("otp")
        try:
            otp = UserOtp.objects.get(otp=otp)
            if otp.is_expired(CARRIER_ADD_OTP_EXPIRATION):
                return Response(
                    {"error": "otp_expired"}, status=status.HTTP_400_BAD_REQUEST
                )
            if not otp.user.email == email:
                return Response(
                    {"error": "no_matching_otp"}, status=status.HTTP_400_BAD_REQUEST
                )
            user = otp.user
            user.role = CARRIER
            profile = user.profile
            vendor = self.request.user.vendor
            otp.delete()
            carrier = Carrier.objects.create(
                user=user, user_profile=profile, vendor=vendor
            )
            user.save()
            # setting carrier live status in redis
            carrier_key = f"carrier:{carrier.id}:live"
            vendor_location = self.request.user.profile.location
            vendor_location = (vendor_location.y, vendor_location.x)
            customer_location = vendor_location
            r.set(
                carrier_key,
                json.dumps(
                    {
                        "return_estimate": 0,
                        "location": vendor_location,
                        "destination": customer_location,
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
    this view is only accessible by a vendor to manage carriers
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
        user.save()


class CarriersNow(views.APIView):
    """this view returns list of vendor carriers sorted by nearst to farthest ones"""

    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def get(self, *args, **kwargs):
        carriers = Carrier.objects.filter(
            vendor__id=self.request.user.vendor.id, is_active=True  # should be changed
        )
        live_vendor_carriers = []  # final list being returned
        for carrier in carriers:
            try:
                carrier_key = f"carrier:{carrier.id}:live"
                carrier_live_data = json.loads(r.get(carrier_key))
                carrier_current_location = carrier_live_data["location"]
                vendor_location = self.request.user.profile.location
                vendor_location = (vendor_location.y, vendor_location.x)
                city = self.request.user.profile.city  # vendor city
                time = 0
                if carrier.status == CARRIER_STATUS_CHOICES[0][0]:  # if carrier is free
                    distance_m = (
                        haversine_distance(*vendor_location, *carrier_current_location)
                        * 1000
                    )  # meters
                    print("distance", distance_m)
                    if distance_m > 100:  # if carrier is not earby the resturant
                        time = estimate_travel_time(
                            carrier_current_location, vendor_location, city
                        )
                else:  # carrier has not reached to customer yet
                    customer_location = carrier_live_data["destination"]
                    time = estimate_travel_time(
                        carrier_current_location, customer_location, "kabul"
                    ) + (carrier_live_data["return_estimate"] / 2)
                details = {"name": carrier.name, "return_time": time}
                live_vendor_carriers.append(details)
                print("appended without error")
            except Exception as e:
                print("error occured while fetching live carriers status", e, e.args)
                details = {"name": carrier.name, "return_time": 0}
                live_vendor_carriers.append(details)

        live_vendor_carriers.sort(
            key=lambda x: int(x["return_time"])
        )  # sorting by nearst to longest carriers
        return Response({"carriers": live_vendor_carriers}, status=status.HTTP_200_OK)


class VendorRevenueView(views.APIView):
    permission_classes = [IsVendor, permissions.IsAuthenticated]

    def get(self, *args, **kwargs):
        """THis view returns vendor revenue"""
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
        this method returns vendor revenue in custom range
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
        start_date = date_parser(start_date)
        end_date = date_parser(end_date)
        if tz.is_naive(start_date):
            start_date = tz.make_aware(date_parser(start_date))  #
        if tz.is_naive(start_date):
            end_date = tz.make_aware(date_parser(end_date))

        vendor = self.request.user.vendor
        # --------------- this month revenue
        orders = Order.objects.filter(
            vendor=vendor,
            status="delivered",
            created_at__gte=start_date,
            created_at__lte=end_date,
        )
        total_revenue = orders.annotate(
            vendor_earning=ExpressionWrapper(
                F("total_items") * PUBLIC_PLATFORM_ITEM_COMMISSION_FEE,
                output_field=DecimalField(),
            )
        ).aggregate(Sum("vendor_earning"))

        return Response({"total-revenue": total_revenue})


class ListVendorOrders(viewsets.ReadOnlyModelViewSet):
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
    input: [id:int, accepted:bool]
    """

    permission_classes = [permissions.IsAuthenticated, IsVendorOfOrder]

    def post(self, *args, **kwargs):
        data = self.request.data
        order_id = data["id"]
        accepted = data["accepted"]

        try:
            order = Order.objects.get(id=order_id)
            # check if this vendor owns the order
            self.check_object_permissions(self.request, order)
            # only 'waiting' order can be set to preparing
            if not order.status == ORDER_STATUS_CHOICES[1][1]:
                return Response(status=status.HTTP_403_FORBIDDEN)
            # accepted
            if accepted == True:
                order.status = ORDER_STATUS_CHOICES[2][1]
                order.save()
                return Response(
                    {"message": "order_accepted"}, status=status.HTTP_200_OK
                )

            # rejected
            # deleting the order
            order.cancel_order()
            # sending notification to customer ....
            return Response({"message": "order_rejected"}, status=status.HTTP_200_OK)

        except Order.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print("error:", e.args, e)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class CalculateOrderTime(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]

    def get(self,*args, **kwargs):
        pass