from rest_framework import permissions as perm
from rest_framework import viewsets, exceptions
from rest_framework import parsers, serializers
from .models import Carrier
from rest_framework.response import Response
from rest_framework import status
from .serializers import CarrierSerializer
from order.serializers import CarrierOrderSerializer
from .permissions import IsBuyer, IsCarrierOfVendor, IsVendor, IsVendorOfCarrier
from order.models import Order
from order.models import ORDER_STATUS_CHOICES
from rest_framework import views

from accounts.models import (
    ADMIN,
    CARRIER_ADD_OTP_EXPIRATION,
    SHOP,
    User,
    UserOtp,
    FOOD_DELIVERY_OTP_EXPIRATION,
    UserProfile,
    CARRIER,
)
from accounts.utils import OTP_VERIFY_CARRIER, generate_otp
from accounts.utils import send_otp

from carrier.models import CARRIER_STATUS_CHOICES


# Create your views here.
class ManageCarrierViewSet(viewsets.ModelViewSet):
    """
    this view is only accessible by a vendor to manage carriers
    GET, PATCH, DELETE
    UPDATEable: is_active, id_document
    """

    permission_classes = [perm.IsAuthenticated, IsVendor, IsVendorOfCarrier]
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


class AddCarrierAPIView(views.APIView): 
    permission_classes = [perm.IsAuthenticated, IsVendor]
    http_method_names = ["post", "patch"]

    def post(self, *args, **kwargs):
        data = self.request.data
        email = data.get("email")
        account = User.objects.filter(email=email).first()
        if not account:
            raise serializers.ValidationError(
                {"error": "no_account_found_by_that_email"}
            )
        if account.role in (SHOP, ADMIN) or account.is_admin:
            raise serializers.ValidationError({"error": "You are not allowed"})
        elif account.role == CARRIER:
            raise serializers.ValidationError({"error": "This carrier is already added"})

        # sending otp
        send_otp(
            self.request,
            account,
            OTP_VERIFY_CARRIER,
            vendor_name=self.request.user.vendor.vendor_name,
        )
        return Response({"message": "otp sent"}, status=status.HTTP_200_OK)

    def patch(self, *args, **kwargs):
        """verifies the otp and creates carrier account"""
        data = self.request.data
        email = data.get("email")
        otp = data.get("otp")
        try:
            otp = UserOtp.objects.get(otp=otp)
            if otp.is_expired(CARRIER_ADD_OTP_EXPIRATION):
                return Response(
                    {"error": "otp expired"}, status=status.HTTP_400_BAD_REQUEST
                )
            if not otp.user.email == email:
                return Response(
                    {"error": "no such otp to you"}, status=status.HTTP_400_BAD_REQUEST
                )
            user = otp.user
            user.role = CARRIER
            profile = user.profile
            vendor = self.request.user.vendor
            Carrier.objects.create(user=user, user_profile=profile, vendor=vendor)
            user.save()
            otp.delete()
            return Response(status=status.HTTP_201_CREATED)

        except UserOtp.DoesNotExist:
            return Response(
                {"error": "no such otp"}, status=status.HTTP_400_BAD_REQUEST
            )
        except:
            return Response(
                {"error": "UKNOWN ERROR"}, status=status.HTTP_400_BAD_REQUEST
            )


class CarrierOrdersApiView(viewsets.ReadOnlyModelViewSet):
    """
    THis view enables a carrier(only) to view list of paid-processing orders
    A carrier can see detail of each
    """

    serializer_class = CarrierOrderSerializer
    permission_classes = [perm.IsAuthenticated, IsCarrierOfVendor]

    def get_queryset(self):
        """overriding to only retrive orders of its vendor"""
        query_set = Order.objects.filter(
            status=ORDER_STATUS_CHOICES[1][1],
            vendor=self.request.user.carrier.vendor,
            paid=True,
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
            if not order.paid:
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
        """carrier sets order status -delivered-"""
        data = self.request.data
        order_id = data.get("order_id")
        input_OTP = str(data.get("otp"))
        try:
            order = Order.objects.get(id=order_id)
            # check if the customer owns this order
            self.check_object_permissions(self.request, order)
            user = order.user
            OTP = UserOtp.objects.get(user=user, otp=input_OTP)
            if OTP.is_expired(expire=FOOD_DELIVERY_OTP_EXPIRATION):
                return Response({"error": "Otp Expired"}, status=400)

            # setting order in submited state and carrier in free state
            order.status = ORDER_STATUS_CHOICES[4][1]  # delivered
            order.carrier.status = CARRIER_STATUS_CHOICES[0][0]  # free
            order.carrier.save()
            order.save()
            return Response(
                {"message": "order state changed to delivered"},
                status=status.HTTP_202_ACCEPTED,
            )
        except Order.DoesNotExist:
            return Response({"error": "No such order"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"error": "Otp Incorrect"}, status=400)
        except exceptions.PermissionDenied:
            return Response(
                {"error": "you are not allowed to perform this action"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"error": "uknown error occured"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
