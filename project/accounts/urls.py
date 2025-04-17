from django.urls import include, path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

app_name = "accounts"

urlpatterns = [
    # accounts
    path("dashboard/", views.dashboard, name="dashboard"),
    path("account-settings/", views.account_settings, name="account_settings"),
    path("profile/", views.profile, name="profile"),
   
]
