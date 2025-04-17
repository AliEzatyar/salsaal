from django.urls import include, path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from order.views import OrderViewSet, OrderItemListAPIView, OrderItemDetailAPIView
from marketplace.views import RatingViewSet, FoodReadViewSet, SearchApiView
from vendor.views import VendorFoodsManageViewSet, VendorAPIView
from carrier.views import CarrierOrdersApiView, CarrierViewSet
from cart.views import CartApiView
from accounts.views import (
    ForgotPassword,
    RegisterUser,
    ResendActivationOTP,
    UpdateDeleteRetriveUser,
    ResetPassword,
    VerifyActivateAccountOTP,
    VerifyForgotPasswordOTP,
)

# Router Setup for
router = DefaultRouter()
# order viewset routing
router.register(r"orders", OrderViewSet)
# rating viewset routing
router.register(r"ratings", RatingViewSet)
# food managemet routing
router.register(r"vendor-foods", VendorFoodsManageViewSet, basename="vendor-foods")
# managing carriers as vendor
router.register(r"carriers", CarrierViewSet)
# router seeing order
router.register(r"carrier-orders", CarrierOrdersApiView, basename="carrier-orders")
# food retrive  routing
router.register(r"foods", FoodReadViewSet)

app_name = "api"

urlpatterns = [
    # Account App
    path("account/generate-token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("account/refresh-token/", TokenRefreshView.as_view(), name="token_refresh"),
    path("account/register/", RegisterUser.as_view(), name="reg_user_api"),
    path(
        "account/activate-account/",
        VerifyActivateAccountOTP.as_view(),
    ),
    path(
        "account/resend-activate-otp/",
        ResendActivationOTP.as_view(),
    ),
    # path("account/register/vendor/", views.register_vendor, name="reg_vend_api"),
    path("account/forgot-password/", ForgotPassword.as_view()),  # send otp
    path(
        "account/forgot-password-verify-otp/", VerifyForgotPasswordOTP.as_view()
    ),  # check otp
    path("account/reset-password/", ResetPassword.as_view()),  # reset password
    # path("account/manage-vendor/", views.manage_vendor, name="manage_vendor"),
    path(
        "account/user-detail/",
        UpdateDeleteRetriveUser.as_view(),
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
    # full search
    path("search/", SearchApiView.as_view(), name="full_search"),
]
