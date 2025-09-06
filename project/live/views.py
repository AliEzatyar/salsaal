from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from live.models import Notification


from .serializers import NotificationSerializer


# Create your views here.
class NotificationReadApiView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        Notification.objects.filter(
            receiver=self.request.user, is_read=False
        ).update(is_read=True)
        user_notf = Notification.objects.filter(receiver=self.request.user).order_by("-date_time")
        notf_ser = NotificationSerializer(user_notf[:15], many=True)
        return Response(notf_ser.data)
