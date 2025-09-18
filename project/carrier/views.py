import json
from django.shortcuts import render
from rest_framework import (
    permissions as perm,
    exceptions,
    views,
    status,
)
from django.utils import timezone as dj_tz
from live.models import Notification
from rest_framework.response import Response
from order.serializers import CarrierOrderSerializer
from api.permissions import (
    IsCarrierOfVendor,
    IsOrderPreparingState,
    IsVendorOfObject,
)
from order.models import Order, ORDER_STATUS_CHOICES
from accounts.models import (
    FOOD_DELIVERY_OTP_EXPIRATION,
)
from carrier.models import CARRIER_STATUS_CHOICES, Carrier
from marketplace.utils import estimate_travel_time_graphhopper
from live.serializers import NotificationSerializer
from carrier.utils import get_carrier_key
from vendor.utils import get_vendor_carriers_key, r
from django.utils.translation import gettext as _
from django.utils.translation import activate as activate_language
from django.utils.translation import deactivate as deactivate_language

# Create your views here.


class CarrierOrderApiView(views.APIView):
    """
    THis view enables a carrier(only) to view list of paid-processing orders
    A carrier can see detail of each
    """

    serializer_class = CarrierOrderSerializer
    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def get(self, *args, **kwargs):
        """carrier only sees an order relating to it, in carrying state and order is created
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
                    # created_at__gte=dj_tz.now() - expire_minutes,
                )
                .order_by("created_at")
                .last()
            )
            if order:
                # check if carrier is of order's vendor
                self.check_object_permissions(self.request, order)
                ser = CarrierOrderSerializer(instance=order)
                return Response({"order": ser.data}, status=status.HTTP_200_OK)
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e, "eroror", e.args)
            return Response(status.HTTP_501_NOT_IMPLEMENTED)



def run_script(request, which=None):
    if which:
        if which == "vendor":
            return render(request, "test_client/vendor.html")
        elif which == "customer":
            return render(request, "test_client/customer.html")

    return render(request, "test_client/carrier.html")
