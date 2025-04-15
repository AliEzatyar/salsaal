from rest_framework import permissions as perm
from rest_framework import viewsets
from rest_framework import parsers
from .models import Carrier

from .serializers import CarrierSerializer, CarrierOrderSerializer
from .permissions import IsCarrierOfVendor, IsVendor
from order.models import Order
from order.serializers import OrderSerializer
from order.models import ORDER_STATUS_CHOICES


# Create your views here.
class CarrierViewSet(viewsets.ModelViewSet):
    """this view is only accessible by a vendor"""
    permission_classes = [perm.IsAuthenticated, IsVendor]
    queryset = Carrier.objects.all()
    serializer_class = CarrierSerializer
    parser_classes = [parsers.JSONParser, parsers.FormParser,parsers.MultiPartParser]
    
    def get_serializer_context(self):
        context =  super().get_serializer_context()
        context["name"] = self.request.user.first_name + self.request.user.first_name
        context["vendor"] = self.request.user.vendor.id

        return context

class CarrierOrdersApiView(viewsets.ReadOnlyModelViewSet):
    """a carrier does custom actions with this view"""

    queryset = Order.objects.filter(status=ORDER_STATUS_CHOICES[1][1])
    serializer_class = CarrierOrderSerializer
    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def get_queryset(self):
        """overriding to only retrive orders of its vendor"""
        query_set = self.queryset.filter(vendor=self.request.user.carrier.vendor)
        return query_set

    # def get(self, *args, **kwargs):
    #     """this mehod enables a carrier see orders list/detail of its vendor"""
    #     obj_id = self.request.query_params.get(["id"], -1)  # order id
    #     if obj_id:
    #         # only one order is seen, goto details
    #         obj = Order.objects.filter(
    #             id=obj_id, status=ORDER_STATUS_CHOICES[1][1]
    #         ).first()
    #         if obj:
    #             self.check_object_permissions(self.request, obj)
    #             serializer = CarrierOrderSerializer(obj)
    #             return Response(serializer.data, status=status.HTTP_200_OK)
    #         return Response(
    #             {"error": "no_object_found"}, status=status.HTTP_400_BAD_REQUEST
    #         )
    #     else:
    #         # all waiting orders are presented
    #         orders = Order.objects.filter(
    #             vendor=self.request.user.carrier.vendor,
    #             status=ORDER_STATUS_CHOICES[1][1],
    #         )  # waiting
    #         serializer = CarrierOrderSerializer(orders, many=True)
    #         return Response(serializer.data, status=status.HTTP_200_OK)
    # def get_serializer_context(self):
    #     return super().get_serializer_context()
