from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from live.models import Notification


from .serializers import NotificationSerializer


# Create your views here.
class NotificationReadApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        notfs = Notification.objects.filter(
            receiver=self.request.user
        )[:30]
        notf_ser = NotificationSerializer(notfs, many=True)
        data = notf_ser.data
        ids = notfs.values_list("id",flat=True)
        Notification.objects.filter(id__in=ids).update(is_read=True)
        return Response(data)
