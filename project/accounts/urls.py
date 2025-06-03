from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "accounts"

# Router Setup for
router = DefaultRouter()
# user profile
router.register(r"user-profile", views.UserProfileViewset, basename="user-profile")
# private user detail
router.register(r"user-detail", views.UserViewset, basename="user-detail")
# public vendor detail


urlpatterns = [
    path("register/", views.RegisterUser.as_view()),
    path(
        "generate-token/",
        views.RoleTokenObtainView.as_view(), name="generate-token"
    ),
    path("refresh-token/", views.RoleTokenRefreshView.as_view()),
    path("activate-account/", views.VerifyActivateAccountOTP.as_view()),
    path("resend-activate-otp/", views.ResendActivationOTP.as_view()),
    path("forgot-password/", views.ForgotPassword.as_view()),  # send otp
    path(
        "forgot-password-verify-otp/",
        views.VerifyForgotPasswordOTP.as_view(),
    ),  # check otp
    path("reset-password/", views.ResetPassword.as_view()),
    path("", include(router.urls)),
]
