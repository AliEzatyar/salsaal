from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "accounts"

# Router Setup for
router = DefaultRouter()
# user profile
# router.register(r"user-profile", views.UserProfileViewset, basename="user-profile")
# private user detail
router.register(r"user-detail", views.UserViewset, basename="user-detail")
router.register(r"user-rewards", views.UserRewardsViewset, basename="user-rewards")

# public vendor detail


urlpatterns = [
    path("login/", views.LoginApiView.as_view(), name="login"),
    path("refresh-token/", views.RoleTokenRefreshView.as_view()),
    path("upsert-device-token/", views.UpsertDeviceToken.as_view()),
    path('delete-account/', views.DeleteAccountView.as_view(), name='delete-account'),
    path("", include(router.urls)),
]
