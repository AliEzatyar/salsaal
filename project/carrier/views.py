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
    IsBuyer,
    IsCarrierOfVendor,
    IsOrderPreparingState,
    IsOrderCarryingState,
    IsVendorOfOrder,
)
from order.models import Order, ORDER_STATUS_CHOICES
from accounts.models import (
    UserOtp,
    FOOD_DELIVERY_OTP_EXPIRATION,
)
from accounts.utils import OTP_VERIFY_CARRIER, generate_otp
from django.contrib.contenttypes.models import ContentType
from carrier.models import CARRIER_STATUS_CHOICES, Carrier
from marketplace.utils import estimate_travel_time
from vendor.utils import r

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
                    created_at__gte=dj_tz.now() - expire_minutes,
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


class SetOrderStateCarrying(views.APIView):
    """
    THis view enables a vendor(only) to choose an order and set it
    in carrying state. Besides, this view generates an OTP valid for 1 Day
    """

    permission_classes = [
        perm.IsAuthenticated,
        IsVendorOfOrder,
        IsOrderPreparingState,
    ]

    def post(self, *args, **kwargs):
        """vendor sets order status -carrying- and generates an OTP"""
        data = self.request.data
        order_id = data.get("order_id")
        carrier_id = data.get("carrier_id")
        try:
            order = Order.objects.get(id=order_id)
            carrier = Carrier.objects.get(pk=carrier_id)
            # vendor should own this carrier
            if carrier.vendor != self.request.user.vendor:
                return Response(status=status.HTTP_403_FORBIDDEN)
            if carrier.status == CARRIER_STATUS_CHOICES[1][0]:
                return Response(
                    {"detail": "carrier_busy"}, status=status.HTTP_409_CONFLICT
                )
            #  vendor should own this order
            self.check_object_permissions(self.request, order)
            # if payment is online and not paid, not allowed
            # if order.is_credit:
            #     if not order.paid:
            #         return Response({"error": "payment not completed"}, status=400)

            user = order.user
            # creating OTP
            OTP = generate_otp()
            UserOtp.objects.create(user=user, otp=OTP)
            # setting order carrier to requesting carrier
            order.carrier = carrier
            carrier.status = CARRIER_STATUS_CHOICES[1][0]  # busy
            # setting order in carrying state
            order.status = ORDER_STATUS_CHOICES[3][1]  # carrying
            order.save()
            carrier.save()
            # setting carrier live status in redis
            carrier_key = f"carrier:{carrier_id}:live"
            vendor_location = self.request.user.profile.location
            vendor_location = (vendor_location.y, vendor_location.x)
            customer_location = order.user.profile.location
            customer_location = (customer_location.y, customer_location.x)
            city = self.request.user.profile.city
            city = city.lower()
            carrier_return_estimate = 2 * estimate_travel_time(
                vendor_location, customer_location
            )
            r.set(
                carrier_key,
                json.dumps(
                    {
                        "return_estimate": carrier_return_estimate,
                        "location": vendor_location,
                        "destination": customer_location,
                    }
                ),
            )
            # ---------------- updating vendor's carriers in redis
            vendor = self.request.user.vendor
            vendor_carriers_key = f"vendor:{vendor.id}:carriers"
            b_c_c = json.loads(r.hget(vendor_carriers_key, "b_c_c"))  # busy carriers count
            b_c_c = int(b_c_c) + 1  # increase it by one
            r.hset(vendor_carriers_key, "b_c_c", b_c_c)  # updating busy carriers count
            f_c_c = json.loads(r.hget(vendor_carriers_key, "f_c_c"))
            f_c_c = int(f_c_c) - 1
            r.hset(vendor_carriers_key, "f_c_c", f_c_c)
            # ---------------------- creating notification
            notf = Notification.objects.create(
                title="Order set as carrying",
                type="order_carrying",
                object_id=order.id,
                ct=ContentType.objects.get_for_model(Order),
                data=json.dumps({}),
            )
            # ---------------------- setting carrier data to redis

            # response
            return Response(
                {
                    "message": "order_status_carrying",
                    "OTP": OTP,
                    "notf_id": notf.id,
                    "customer_id": order.user.id,
                },
                status=status.HTTP_201_CREATED,
            )

        except Order.DoesNotExist:
            return Response({"error": "no such order"}, status=404)
        except exceptions.PermissionDenied as pd:
            print(pd, pd.args)
            return Response({"error": "not_allowed"}, status=403)

        # except Exception as e:
        #     print("error:", e, e.args)

        #     return Response(
        #         {"detail", "unkown_error"}, status=status.HTTP_501_NOT_IMPLEMENTED
        #     )


class SetOrderStateDelivered(views.APIView):
    """
    This view is only accessible via customer account, it proves whether
    a customer (indirectly-by-scanning) is the owner of order and valid Food has reached it.
    """

    permission_classes = [perm.IsAuthenticated, IsBuyer, IsOrderCarryingState]

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
            OTP.delete()
            order.save()
            # ---------------- updating vendor's carriers in redis
            vendor = order.vendor
            vendor_carriers_key = f"vendor:{vendor.id}:carriers"
            b_c_c = r.hget(vendor_carriers_key, "b_c_c")  # busy carriers count
            b_c_c = int(b_c_c) - 1  # decrementing busy carrier's count
            r.hset(vendor_carriers_key, "b_c_c",b_c_c)  # updating busy carriers count
            f_c_c = r.hget(vendor_carriers_key, "f_c_c")
            f_c_c = int(f_c_c) + 1  # incrementing free carrier's count
            r.hset(vendor_carriers_key, "f_c_c", f_c_c)
            return Response(
                {
                    "message": "order_state_delivered",
                    "customer_name": order.user.get_full_name(),
                },
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
            print("error:", e, e.args)
            return Response(
                {"error": "uknown error occured"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )


def run_script(request,which=None):
    if which:
        if which == "vendor":
            return render(request,"test_client/vendor.html")
        elif which == "customer":
            return render(request, "test_client/customer.html")

    return render(request, "test_client/carrier.html")
