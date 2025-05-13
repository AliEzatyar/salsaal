from marketplace.models import Food
from carrier.permissions import IsVendor, IsVendorOfOrder
from order.serializers import VOrderSerializer
from order.models import ORDER_STATUS_CHOICES, Order
from multiVend.settings.base import PUBLIC_PLATFORM_ITEM_COMMISSION_FEE
from accounts.models import CUSTOMER, SHOP
from .serializers import VendorSerializerDetailed
from api.backends import FoodFilterSet, VOrderFilterSet
from marketplace.serializers import FoodSerializerDetail
from api.permissions import IsVendorOfFood

from rest_framework import permissions
from rest_framework import viewsets
from rest_framework import views
from rest_framework import status
from rest_framework.response import Response
from rest_framework import filters
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone as tz
from dateutil.parser import parser as date_parser
from django_filters.rest_framework import DjangoFilterBackend

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
        user.role = CUSTOMER
        vendor.delete()
        user.save()
        return Response(status=status.HTTP_200_OK)


class ConvertToVendorAPIView(views.APIView):
    http_method_names = ["post"]

    def post(self, *args, **kwargs):
        """
        THis method converts a user to a vendor account
        body: vendor_name
        """
        # if user is already a vendor
        if self.request.user.role == SHOP or hasattr(self.request.user, "vendor"):
            return Response(
                {"error": "user already a vendor"}, status=status.HTTP_403_FORBIDDEN
            )

        data = self.request.data
        ser = VendorSerializerDetailed(data=data, context={"request": self.request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


class VendorFoodsManageViewSet(viewsets.ModelViewSet):
    """this class enables CRUD operations on foods of a vendor"""

    serializer_class = FoodSerializerDetail
    permission_classes = [permissions.IsAuthenticated, IsVendorOfFood]
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
            order.objects.delete()
            # sending notification to customer ....
            return Response({"message": "order_rejected"}, status=status.HTTP_200_OK)

        except Order.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)
