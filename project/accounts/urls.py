from django.urls import include, path
from . import views
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
    path("account-settings/", views.account_settings, name="account_settings"),
    path("profile/", views.profile, name="profile"),
   
]
