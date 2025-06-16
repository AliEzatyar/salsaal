from rest_framework import (
    permissions as perm,
    viewsets,
    exceptions,
    views,
    status,
)
from live.models import Notification
from rest_framework.response import Response
from order.serializers import CarrierOrderSerializer
from api.permissions import IsBuyer, IsCarrierOfVendor
from order.models import Order, ORDER_STATUS_CHOICES
from accounts.models import (
    UserOtp,
    FOOD_DELIVERY_OTP_EXPIRATION,
)
from accounts.utils import OTP_VERIFY_CARRIER, generate_otp
from django.contrib.contenttypes.models import ContentType
from carrier.models import CARRIER_STATUS_CHOICES


# Create your views here.


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
            status=ORDER_STATUS_CHOICES[2][1],  # preparing
            vendor=self.request.user.carrier.vendor,
            # paid=True,
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
            # if payment is online and not paid, not allowed
            if order.is_credit:
                if not order.paid:
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
            # ---------------------- creating notification
            notf = Notification.objects.create(
                title="Order set as carrying",
                type="order_carrying",
                object_id=order.id,
                ct=ContentType.objects.get_for_model(Order),
                to=order.vendor.id,
            )

            # response
            return Response(
                {"message": "order_status_carrying", "OTP": OTP},
                status=status.HTTP_201_CREATED,
            )

        except Order.DoesNotExist:
            return Response({"error": "no such order"}, status=404)


class SetOrderStateDelivered(views.APIView):
    """
    This view is only accessible via customer account, it proves whether
    a customer (indirectly-by-scanning) is the owner of order and valid Food has reached it.
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

            # check if otp is correct
            user = order.user
            OTP = UserOtp.objects.filter(user=user, otp=input_OTP).first()
            if not OTP:
                return Response({"error": "otp_incorrect"}, status=400)
            if OTP.is_expired(expire=FOOD_DELIVERY_OTP_EXPIRATION):
                return Response({"error": "otp_expired"}, status=400)

            # setting order in submited state and carrier in free state
            order.status = ORDER_STATUS_CHOICES[4][1]  # delivered
            order.carrier.status = CARRIER_STATUS_CHOICES[0][0]  # free
            order.carrier.save()
            order.paid = True
            order.save()
            return Response(
                {"message": "order_state_delivered"},
                status=status.HTTP_202_ACCEPTED,
            )
        except Order.DoesNotExist:
            return Response({"error": "no_macthing_order"}, status=404)
        except UserOtp.DoesNotExist:
            return Response({"error": "invalid_otp"}, status=400)
        except exceptions.PermissionDenied:
            return Response(
                {"error": "not_allowed"},
                status=status.HTTP_403_FORBIDDEN,
            )
        except Exception as e:
            return Response(
                {"error": "uknown error occured"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )
