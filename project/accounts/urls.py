from django.urls import include, path
from . import views
from .api import api_views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

app_name = "accounts"

urlpatterns = [
    # accounts
    path("register", views.register_user, name="reg_user"),
    path(
        "activate-account/<uidb64>/<token>/",
        views.activate_user_account,
        name="activate",
    ),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path(
        "reset-password-validate/<uidb64>/<token>/",
        views.reset_password_validate,
        name="reset_password_validate",
    ),
    path("reset-password/", views.reset_password, name="reset_password"),
    # authentication
    path("login/", views.login, name="login"),
    path("login/<str:next>/", views.login, name="login_next"),
    path("logout/", views.logout, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("customer-dashboard/", views.customer_dashboard, name="customer_dashboard"),
    # rest
    path("api/generate-token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("api/refresh-token/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/register/", api_views.RegisterUser.as_view(), name="reg_user_api"),
    path("api/register/vendor/", api_views.register_vendor, name="reg_vend_api"),
    path("api/forgot-password/", api_views.forgot_password),
    path("api/manage-vendor/", api_views.manage_vendor, name="manage_vendor"),
    path(
        "api/user-detail/",
        api_views.UpdateDeleteRetriveUser.as_view(),
        name="user_detail",
    ),
    # vendor app urls
]
