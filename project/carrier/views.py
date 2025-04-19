from rest_framework import permissions as perm
from rest_framework import viewsets, exceptions
from rest_framework import parsers
from .models import Carrier
from rest_framework.response import Response
from rest_framework import status
from .serializers import CarrierSerializer, CarrierOrderSerializer
from .permissions import IsBuyer, IsCarrierOfVendor, IsVendor
from order.models import Order
from order.models import ORDER_STATUS_CHOICES, PAYMENT_STATUS_CHOICES
from rest_framework import views
from accounts.models import User, UserOtp, FOOD_OTP_EXPIRATION, UserProfile, CARRIER
from accounts.utils import generate_otp

from carrier.models import CARRIER_STATUS_CHOICES


# Create your views here.
class CarrierViewSet(viewsets.ModelViewSet):
    """this view is only accessible by a vendor to manage carriers"""

    permission_classes = [perm.IsAuthenticated, IsVendor]
    queryset = Carrier.objects.all()
    serializer_class = CarrierSerializer
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]

    def get_serializer_context(self):
        context = super(CarrierViewSet,self).get_serializer_context()
        context["vendor"] = self.request.user.vendor.id
        return context


class CarrierOrdersApiView(viewsets.ReadOnlyModelViewSet):
    """
        THis view enables a carrier(only) to view list of paid-processing orders
        A carrier can see detail of each
    """

    queryset = Order.objects.filter(status=ORDER_STATUS_CHOICES[1][1])
    serializer_class = CarrierOrderSerializer
    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def get_queryset(self):
        """overriding to only retrive orders of its vendor"""
        query_set = self.queryset.filter(
            vendor=self.request.user.carrier.vendor, paid=True
        )
        return query_set


class SetOrderStateCarrying(views.APIView):
    """
        THis view enables a carrier(only) to choose an order and set it 
        in carrying state. Besides, this view generates an OTP valid for 1 Day
    """
    
    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def post(self, *args, **kwargs):
        """carrier sets order status -carrying- and generates an OTP"""
        data = self.request.data
        order_id = data.get("order_id")
        try:
            order = Order.objects.get(id=order_id)
            if order.payment_status == PAYMENT_STATUS_CHOICES[1][1] or not order.paid :
                # not paid
                return Response({"error": "payment not completed"}, status=400)
            self.check_object_permissions(self.request, order)
            user = order.user
            # creating OTP
            OTP = generate_otp()
            UserOtp.objects.create(user=user, otp=OTP)
            # setting order carrier to requesting carrier
            order.carrier = self.request.user.carrier
            order.carrier.status = CARRIER_STATUS_CHOICES[1][0]  # busy
            # setting order in carrying state
            order.status = ORDER_STATUS_CHOICES[3][1]  # carrying
            order.save()
            # response
            return Response(
                {"message": "order_status_carrying", "OTP": OTP},
                status=status.HTTP_201_CREATED,
            )

        except Order.DoesNotExist:
            return Response({"error": "no such order"}, status=404)


class SetOrderStateSubmitted(views.APIView):
    """
        This view is only accessible via customer account, it proves whether
        a customer (indirectly-by-scanning) is the owner of order and valid Food has reached it
    """

    permission_classes = [perm.IsAuthenticated, IsBuyer]

    def post(self, *args, **kwargs):
        """carrier sets order status -submitted-"""
        data = self.request.data
        order_id = data.get("order_id")
        input_OTP = str(data.get("otp"))
        try:
            order = Order.objects.get(id=order_id)
            # check if the customer owns this order
            self.check_object_permissions(self.request, order)
            user = order.user
            OTP = UserOtp.objects.get(user=user, otp=input_OTP)
            if OTP.is_expired(expire=FOOD_OTP_EXPIRATION):
                return Response({"error": "Otp Expired"}, status=400)

            # setting order in submited state and carrier in free state
            order.status = ORDER_STATUS_CHOICES[4][1]  # submitted
            order.carrier.status = CARRIER_STATUS_CHOICES[0][0]  # free
            order.carrier.save()
            order.save()
            return Response({"message":"order state changed to submitted"},status=status.HTTP_202_ACCEPTED)
        except Order.DoesNotExist:
            return Response({"error": "No such order"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"error": "Otp Incorrect"}, status=400)
        except exceptions.PermissionDenied:
            return Response({"error":"you are not allowed to perform this action"},status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response(
                {"error": "uknown error occured"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
