from django.urls import include, path
from . import views
from .api import api_views
from  rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
app_name = 'accounts'

urlpatterns = [
    path("register-resturant", views.register_rest, name="reg_res"),
    path("register", views.register_user, name="reg_user"),
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


