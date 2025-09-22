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
from accounts.models import (
    FOOD_DELIVERY_OTP_EXPIRATION,
)
from django.utils.translation import gettext as _

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
                minutes=FOOD_DELIVERY_OTP_EXPIRATION
            )  # 3 hours
            order = (
                Order.objects.filter(
                    status=ORDER_STATUS_CHOICES[3][0],  # carrying
                    carrier=self.request.user.carrier,
                    created_at__gte=dj_tz.now() - expire_minutes,
                )
                .last()
            )
            if order:
                # check if carrier is of order's vendor
                self.check_object_permissions(self.request, order)
                ser = CarrierOrderSerializer(instance=order)
                return Response(ser.data, status=status.HTTP_200_OK)
            return Response(status=status.HTTP_404_NOT_FOUND)
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
            .only("id", "user", "paid", "created_at") # should match serializer fields
        )
        ser = CarrierOrderSerializerMany(orders, many=True)
        return Response(ser.data,status=status.HTTP_200_OK)


def run_script(request, which=None):
    if which:
        if which == "vendor":
            return render(request, "test_client/vendor.html")
        elif which == "customer":
            return render(request, "test_client/customer.html")

    return render(request, "test_client/carrier.html")
