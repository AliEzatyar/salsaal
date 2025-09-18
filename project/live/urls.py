from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "live"

# Router Setup for


urlpatterns = [
    path("read-notifications/", views.NotificationReadApiView.as_view()),
    
]
