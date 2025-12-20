from typing import Any
from rest_framework import views, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Prefetch
from api.permissions import IsCustomer, IsVendor, IsVendorOfObject
from accounts.models import User
from qoraa.models import MIN_QORAA_PRICE_VALUE, Qoraa
from .serializers import (
    QoraaReadOnlySerializer,
    VendorQoraaFoodSerializer,
    VendorQoraaSerializer,
)

# Create your views here.


class ListQoraaApiView(views.APIView):
    """
    A simple ViewSet for viewing active and past qoraas.
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get(self, request, *args, **kwargs):
        """Returns a list of active qoraas."""
        now = timezone.now()
        one_day_ago = now - timezone.timedelta(days=1)
        qoraas = (
            Qoraa.objects.filter(
                start__lte=now,
                end__gte=one_day_ago,
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
