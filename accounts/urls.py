from django.urls import include, path
from . import views
from .api import api_views
from  rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
app_name = 'accounts'

urlpatterns = [
    path("register-vendor", views.register_vendor, name="reg_vend"),
    path("register", views.register_user, name="reg_user"),
    # authentication
    path("login/", views.login, name="login"),
    path("logout/", views.logout, name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("customer-dashboard/", views.customer_dashboard, name="customer_dashboard"),
    path("vendor-dashboard/", views.vend_dashboard, name="vend_dashboard"),
    # rest
    path("api/generate-token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("api/refresh-token/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/register/", api_views.RegisterUser.as_view(), name="reg_user_api"),
    path(
        "api/user-detail/",
        api_views.UpdateDeleteRetriveUser.as_view(),
        name="user_detail",
    ),
]
