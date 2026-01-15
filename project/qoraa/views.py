from typing import Any
from rest_framework import views, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Prefetch
from api.permissions import IsCustomer, IsVendor, IsVendorOfObject
from accounts.models import User, UserOtp
from order.models import ORDER_STATUS_CHOICES, VALID_PAYMENT_TYPES, Order, OrderItem
from accounts.utils import generate_otp
from live.utils import push_notification
from qoraa.models import MIN_QORAA_PRICE_VALUE, Qoraa
from .serializers import (
    QoraaReadOnlySerializer,
    VendorQoraaFoodSerializer,
    VendorQoraaSerializer,
)
from django.contrib.gis.geos import Point

from django.utils.translation import gettext as _
from django.utils.translation import deactivate as deactivate_language
from django.utils.translation import activate as activate_language
from logging import getLogger

logger = getLogger(__name__)


# Create your views here.


class ListQoraaApiView(views.APIView):
    """
    A simple ViewSet for viewing active and past qoraas.
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get(self, request, *args, **kwargs):
        """Returns a list of active qoraas."""
        now = timezone.now()
        six_hour_ago = now - timezone.timedelta(hours=6)
        qoraas = (
            Qoraa.objects.filter(
                start__lte=now,
                end__gte=six_hour_ago,
                status__in=[Qoraa.STATUS_RUNNING, Qoraa.STATUS_FINISHED],
            )
            .prefetch_related(Prefetch("joiners", queryset=User.objects.only("id")))
            .order_by("-price_value")
        )
        ser = QoraaReadOnlySerializer(qoraas, many=True, context={"request": request})
        return Response(ser.data, status=status.HTTP_200_OK)


class JoinQoraaApiView(views.APIView):
    """
    Allow authenticated users to join the currently active lottery.
    Users can join at most once per lottery. The user object is taken from request.user.
    """

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        """enables a user to join a specific active lottery."""
        now = timezone.now()
        qoraa_id = request.data.get("qoraa_id")
        q = None
        if not qoraa_id:
            return Response(
                {"detail": "qoraa_id_required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            q = Qoraa.objects.get(
                pk=qoraa_id,
                start__lte=now,
                end__gt=now,
                status=Qoraa.STATUS_RUNNING,
            )
        except Qoraa.DoesNotExist:
            return Response(
                {"detail": "no_active_lottery_with_id"},
                status=status.HTTP_404_NOT_FOUND,
            )
        # --- check if user already joined --> handle UI
        if q.joiners.count() >= q.joiners_limit:
            return Response(
                {"detail": "joiners_limit_reached"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if q.vendor.user_profile.city != request.user.profile.city:
            return Response(
                {"detail": "user_and_vendor_city_mismatch"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        added = q.add_joiner(request.user)
        if not added:
            return Response(
                {"detail": "already_joined"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"detail": "joined"}, status=status.HTTP_200_OK)


class GetFoodsForQoraaApiView(views.APIView):
    """
    Vendors can get their food items eligible for Qoraa participation.
    """

    permission_classes = [IsAuthenticated, IsVendor]

    def get(self, request, *args, **kwargs):
        """Returns a list of food items for the vendor."""
        vendor = request.user.vendor
        foods = vendor.foods.all()
        ser = VendorQoraaFoodSerializer(foods, many=True)
        food_list = ser.data # list
        data = {"foods": food_list, "price_limit": MIN_QORAA_PRICE_VALUE}
        return Response(data, status=status.HTTP_200_OK)


class ManageQoraaViewset(viewsets.ModelViewSet):
    """
    Vendors can create or update their qoraas.
    This uses an update_or_create logic to be idempotent.
    """

    serializer_class = VendorQoraaSerializer
    permission_classes = [IsAuthenticated, IsVendorOfObject]

    def get_queryset(self):
        return Qoraa.objects.filter(vendor=self.request.user.vendor)

    def get_serializer_context(self, **kwargs) -> dict[str, Any]:
        context = super().get_serializer_context(**kwargs)
        context["vendor"] = self.request.user.vendor.id
        return context

    def perform_destroy(self, instance):
        if instance.status not in [Qoraa.STATUS_SCHEDULED,Qoraa.STATUS_FINISHED]:
            return Response(
                {"detail": "only_pending_qoraa_can_be_deleted"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().perform_destroy(instance)


class ClaimQoraaPrizeApiView(views.APIView):
    """
    Customers who have won a Qoraa can claim their prize, which creates an order for them.
    """

    permission_classes = [IsAuthenticated, IsCustomer]

    def post(self, request, *args, **kwargs):
        """Allows a user to claim their prize for a specific ."""
        # ----------------- updating user's location
        data = request.data
        lat = data.get("latitude", None)
        lon = data.get("longitude", None)
        qoraa_id = data.get("qoraa_id")
        if lat and lon:
            try:

                float(lat)
                float(lon)
            except ValueError:
                return Response(
                    {"detail": "provide_correct_location"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user_profile = request.user.profile
            user_profile.latitude = str(lat)
            user_profile.longitude = str(lon)
            user_profile.save()
        else:
            return Response(
                {"detail": "provide_correct_location"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not qoraa_id:
            return Response(
                {"detail": "qoraa_id_required"}, status=status.HTTP_400_BAD_REQUEST
            )
        q = None
        try:
            q = Qoraa.objects.get(pk=qoraa_id, status=Qoraa.STATUS_FINISHED, winner=request.user)
            if q.is_claimed:
                return Response(
                    {"detail": "prize_already_claimed"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            logger.error(f"Error fetching finished Qoraa for user {request.user.id}: qoraa_id {qoraa_id}: {e}")
            return Response(
                {"detail": "no_finished_lottery_with_id"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # creating the order and setting in preparing state
        otp = generate_otp(8)
        UserOtp.objects.create(user=request.user, otp=otp)
        new_order = Order.objects.create(
            user=request.user,
            status=ORDER_STATUS_CHOICES[2][0],  # preparing
            total_price=0,
            total_items=1,
            delivery_cost=0,
            paid=True,
            otp=otp,
            destination=Point(float(request.user.profile.latitude), float(request.user.profile.longitude), srid=4326),
            vendor=q.vendor,
            payment_type=VALID_PAYMENT_TYPES[3][0],  # qoraa_payment
            is_epay=False,
        )
        # creating the order item for the won food
        OrderItem.objects.create(
            order=new_order,
            food=q.food,
            quantity=1,
            price=q.price_value,
            vendor=q.vendor,
        )
        q.is_claimed = True
        q.save()
        # sending notificaiton to vendor
        activate_language(q.vendor.user_profile.pf_lang)
        push_notification(
            user_id=q.vendor.user.id,
            title=_("Qoraa Prize Claimed"),
            body=_(f"The Qoraa winner has claimed their prize. Order ID: {new_order.id}. Please prepare the order and deliver it."),
            data={"order_id": new_order.id}
        )
        deactivate_language()
        return Response({"detail": "prize_claimed"}, status=status.HTTP_200_OK)
