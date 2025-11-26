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
    API view for carriers to view their current order.
    This view allows a carrier to see the details of the order they are currently carrying.
    Only orders created within the last 3 hours are considered.
    """

    serializer_class = CarrierOrderSerializer
    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def get(self, *args, **kwargs):
        """
        Retrieve the current order for the authenticated carrier.

        Returns:
            - Order details if a valid order exists.
            - Vendor details associated with the carrier.
        """
        try:
            order = (
                Order.objects.filter(
                    status=ORDER_STATUS_CHOICES[3][0],  # carrying
                    carrier=self.request.user.carrier,
                )
                .prefetch_related("items")
                .first()
            )
            current_order_data = None
            carrier_vendor = self.request.user.carrier.vendor
            if order:
                # Ensure the carrier has permission to access the order
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
        except perm.exceptions.PermissionDenied:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"detail": "An error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeliveredOrdersApiView(views.APIView):
    """
    API view for carriers to view their delivered orders.

    This view provides a paginated list of orders that have been delivered by the carrier.
    """

    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def get(self, *args, **kwargs):
        """
        Retrieve a paginated list of delivered orders for the authenticated carrier.

        Returns:
            - Paginated response containing delivered orders.
        """
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
    """
    Render a test client page based on the `which` parameter.

    Args:
        request: The HTTP request object.
        which: Specifies the type of client to render (vendor, customer, or carrier).

    Returns:
        - Rendered HTML page for the specified client type.
        - 400 Bad Request if the `which` parameter is invalid.
    """
    allowed_values = {"vendor", "customer", "carrier"}
    if which not in allowed_values:
        return Response({"detail": "Invalid parameter."}, status=status.HTTP_400_BAD_REQUEST)

    if which == "vendor":
        return render(request, "test_client/vendor.html")
    elif which == "customer":
        return render(request, "test_client/customer.html")

    return render(request, "test_client/carrier.html")
