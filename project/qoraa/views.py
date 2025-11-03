from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from qoraa.utils import get_city_lottery_vendors_key
from vendor.models import Vendor
from .models import Qoraa
from marketplace.utils import r

# Create your views here.


class CurrentQoraaApiView(views.APIView):
    """
    Return the active/current Qoraa (lottery) if exists.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        q = Qoraa.objects.filter(start__lte=now, end__gt=now).order_by("-start").first()
        if not q:
            return Response(
                {"detail": "no_active_lottery"}, status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "id": q.pk,
                "title": q.title,
                "start": q.start,
                "end": q.end,
                "joiners_count": q.joiners.count(),
                "status": q.status,
            }
        )


class JoinQoraaApiView(views.APIView):
    """
    Allow authenticated users to join the currently active lottery.

    Users can join at most once per lottery. The user object is taken from request.user.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        now = timezone.now()
        q = (
            Qoraa.objects.filter(
                start__lte=now, end__gt=now, status=Qoraa.STATUS_RUNNING
            )
            .order_by("-start")
            .first()
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


class AddQoraaVendor(views.APIView):
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

        key = get_city_lottery_vendors_key()
        r.sadd(key, str(vendor.pk))
        return Response({"detail": "vendor_added"}, status=status.HTTP_200_OK)
