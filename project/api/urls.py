from django.urls import include, path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from .views import (
    OrderItemDetailAPIView,
    OrderItemListAPIView,
    OrderViewSet,
    ProductReadViewSet,
    RatingViewSet,
    CartApiView,
    VendorAPIView,
    VendorProductsManageViewSet,
)


# Router Setup for
router = DefaultRouter()
# order viewset routing
router.register(r"orders", OrderViewSet)
# rating viewset routing
router.register(r"ratings", RatingViewSet)
# product managemet routing
router.register(
    r"vendor-products", VendorProductsManageViewSet, basename="vendor-products"
)
# product retrive  routing
router.register(r"products",ProductReadViewSet)

app_name = "api"

urlpatterns = [
    # Account App
    path("account/generate-token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("account/refresh-token/", TokenRefreshView.as_view(), name="token_refresh"),
    path("account/register/", views.RegisterUser.as_view(), name="reg_user_api"),
    path("account/forgot-password/", views.forgot_password),
    path(
        "account/user-detail/",
        views.UpdateDeleteRetriveUser.as_view(),
        name="user_detail",
    ),
    # Order and Product
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

