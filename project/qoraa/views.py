from rest_framework import views, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from api.permissions import IsCustomer, IsVendor
from qoraa.serializers import QoraaVendorSerializer
from vendor.models import Vendor
from .models import Qoraa, QoraaVendor, MIN_QORAA_PRICE_VALUE
from .serializers import QoraaReadOnlySerializer

# Create your views here.


class QoraaListApiView(views.APIView):
    """
    A simple ViewSet for viewing active and past qoraas.
    """

    def get(self, request, *args, **kwargs):
        """Returns a list of active qoraas."""
        now = timezone.now()
        qoraas = Qoraa.objects.filter(start__lte=now, end__gte=now,status__in=[Qoraa.STATUS_RUNNING,Qoraa.STATUS_FINISHED]
                                                                               ).prefetch_related("joiners").order_by("-price_value")
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
        if qoraa_id:
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
        else:
            return Response(
                {"detail": "qoraa_id_required"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not q:
            return Response(
                {"detail": "no_active_lottery"}, status=status.HTTP_404_NOT_FOUND
            )

        added = q.add_joiner(request.user)
        if not added:
            return Response(
                {"detail": "already_joined"}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"detail": "joined"}, status=status.HTTP_200_OK)


class JoinQoraaVendor(views.APIView):
    """
    Vendors can join or update their qoraa participation settings.
    This uses an update_or_create logic to be idempotent.
    """
    
    permission_classes = [IsAuthenticated, IsVendor]

    def post(self, request, *args, **kwargs):
        vendor_id = request.data.get("vendor_id")
        if not vendor_id:
            return Response(
                {"detail": "vendor_id_required"}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            return Response(
                {"detail": "vendor_not_found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception:
            return Response(
                {"detail": "invalid_vendor_id"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Use update_or_create to handle both creation and updates

        if (
            not request.data.get("food_items", None)
            or len(request.data.get("food_items")) == 0
        ):
            return Response(
                {"detail": "food_items_required"}, status=status.HTTP_400_BAD_REQUEST
            )
        ser = QoraaVendorSerializer(data=request.data)
        if ser.is_valid(raise_exception=True):
            qoraa_vendor, created = QoraaVendor.objects.update_or_create(
                vendor=vendor,
                defaults={
                    "title": request.data.get("title", "Daily Lottery"),
                    "food_items": request.data.get("food_items", []),
                    "is_active": request.data.get("is_active", True),
                    "price_value": request.data.get("price_value", MIN_QORAA_PRICE_VALUE),
                },
            )
            response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
            return Response(ser.data, status=response_status)
        else:
            return Response(
                {"detail": "invalid_data"}, status=status.HTTP_400_BAD_REQUEST
            )
