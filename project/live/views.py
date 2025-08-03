from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from live.models import Notification

from .serializers import NotificationSerializer

# Create your views here.
class NotificationReadViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """only notification of the requesting user is returned"""
        return Notification.objects.filter(receiver=self.request.user)