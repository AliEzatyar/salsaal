from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "live"

# Router Setup for
router = DefaultRouter()
# user profile
# router.register(r"user-profile", views.UserProfileViewset, basename="user-profile")
# private user detail
router.register(r"user-notifications", views.NotificationReadViewset, basename="user-notifications")
# public vendor detail


urlpatterns = [
    path("", include(router.urls)),
]
