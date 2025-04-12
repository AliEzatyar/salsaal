from django.urls import include, path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from .views import (
    OrderItemDetailAPIView,
    OrderItemListAPIView,
    OrderViewSet,
    FoodReadViewSet,
    RatingViewSet,
    CartApiView,
    VendorAPIView,
    VendorFoodsManageViewSet,
)


# Router Setup for
router = DefaultRouter()
# order viewset routing
router.register(r"orders", OrderViewSet)
# rating viewset routing
router.register(r"ratings", RatingViewSet)
# food managemet routing
router.register(
    r"vendor-foods", VendorFoodsManageViewSet, basename="vendor-foods"
)
# food retrive  routing
router.register(r"foods",FoodReadViewSet)

app_name = "api"

urlpatterns = [
    # Account App
    path("account/generate-token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("account/refresh-token/", TokenRefreshView.as_view(), name="token_refresh"),
    path("account/register/", views.RegisterUser.as_view(), name="reg_user_api"),
    path("account/register/vendor/", views.register_vendor, name="reg_vend_api"),
    path("account/forgot-password/", views.forgot_password),
    path("account/manage-vendor/", views.manage_vendor, name="manage_vendor"),
    path(
        "account/user-detail/",
        views.UpdateDeleteRetriveUser.as_view(),
        name="user_detail",
    ),
    # Order and Food
    path("", include(router.urls)),
    path(
        "orders/<int:order_id>/items/",
        OrderItemListAPIView.as_view(),
        name="order-item-list",
    ),
    path(
        "orders/item-detail/<int:item_id>/",
        OrderItemDetailAPIView.as_view(),
        name="order-item-detail",
    ),
    # cart
    path(
        "cart/",
        CartApiView.as_view(),
        name="cart-detail",
    ),
    # vendor
    path(
        "vendor/",
        VendorAPIView.as_view(),
        name="vendor",
    ),
]

