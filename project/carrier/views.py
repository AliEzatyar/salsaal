from django.shortcuts import render
from rest_framework import (
    permissions as perm,
    views,
    status,
)
from django.utils import timezone as dj_tz
from rest_framework.response import Response
from api.permissions import (
    IsCarrierOfVendor,
)
from order.models import Order, ORDER_STATUS_CHOICES
from order.models import (
    ORDER_DELIVERY_OTP_EXPIRATION,
)
from django.utils.translation import gettext as _

from marketplace.utils import StandardResultSetPagination
from .serializers import CarrierOrderSerializerMany, CarrierOrderSerializer

# Create your views here.


class CarrierOrderApiView(views.APIView):
    """
    THis view enables a carrier(only) to view current order it carries.
    A carrier can see detail of each
    """

    serializer_class = CarrierOrderSerializer
    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def get(self, *args, **kwargs):
        """carrier only sees an order relating to it, in carrying state and the order is created
        late than 3 hours ago. If multiple, then last one is returned.
        """
        try:
            expire_minutes = dj_tz.timedelta(
                minutes=ORDER_DELIVERY_OTP_EXPIRATION
            )  # 3 hours
            order = (
                Order.objects.filter(
                    status=ORDER_STATUS_CHOICES[3][0],  # carrying
                    carrier=self.request.user.carrier,
                    created_at__gte=dj_tz.now() - expire_minutes,
                )
                .prefetch_related("items")
                .last()
            )
            current_order_data = None
            carrier_vendor = self.request.user.carrier.vendor
            if order:
                # check if carrier is of order's vendor
                self.check_object_permissions(self.request, order)
                ser = CarrierOrderSerializer(instance=order)
                current_order_data = ser.data
            data = {
                "current_order": current_order_data,
                "vendor": {
                    "name": carrier_vendor.vendor_name,
                    "image": carrier_vendor.image.url,
                    "address": carrier_vendor.user_profile.address,
                },
            }
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e, "eroror", e.args)  
            return Response(status.HTTP_501_NOT_IMPLEMENTED)


class DeliveredOrdersApiView(views.APIView):
    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def get(self, *args, **kwargs):
        orders = (
            Order.objects.filter(
                status=ORDER_STATUS_CHOICES[4][0],  # delivered
                carrier=self.request.user.carrier,
            )
            .select_related("user")
            .only("id", "user", "paid", "created_at")  # should match serializer fields
        )
        pg = StandardResultSetPagination(10)
        page_orders = pg.paginate_queryset(orders, self.request)
        ser = CarrierOrderSerializerMany(page_orders, many=True)
        return pg.get_paginated_response(ser.data)


def run_script(request, which=None):
    if which:
        if which == "vendor":
            return render(request, "test_client/vendor.html")
        elif which == "customer":
            return render(request, "test_client/customer.html")

    return render(request, "test_client/carrier.html")
