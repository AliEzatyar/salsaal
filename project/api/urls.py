from django.urls import include, path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from order.views import OrderViewSet, OrderItemListAPIView, OrderItemDetailAPIView
from marketplace.views import RatingViewSet, MarketplaceViewset, SearchApiView
from vendor.views import VendorFoodsManageViewSet, VendorAPIView
from carrier.views import CarrierOrdersApiView, CarrierViewSet, SetOrderStateCarrying, SetOrderStateSubmitted
from cart.views import CartApiView

from accounts import views as ac_views

# Router Setup for
router = DefaultRouter()
# order viewset routing
router.register(r"orders", OrderViewSet)
# user profile
router.register(r"user-profile", ac_views.UserProfileViewset)
# user detail 
router.register(r"user-detail", ac_views.UserViewset)

# rating viewset routing
router.register(r"ratings", RatingViewSet)
# food managemet routing
router.register(r"vendor-foods", VendorFoodsManageViewSet, basename="vendor-foods")
# managing carriers as vendor
router.register(r"carriers", CarrierViewSet)
# router seeing order
router.register(r"carrier-orders", CarrierOrdersApiView, basename="carrier-orders")
# food retrive  routing
router.register(r"foods", MarketplaceViewset)

app_name = "api"

urlpatterns = [
    # Account App
    path("account/generate-token/", TokenObtainPairView.as_view(), name="token_obtain"),
    path("account/refresh-token/", TokenRefreshView.as_view(), name="token_refresh"),
    path("account/register/", ac_views.RegisterUser.as_view(), name="reg_user_api"),
    path(
        "account/activate-account/",
        ac_views.VerifyActivateAccountOTP.as_view(),
    ),
    path(
        "account/resend-activate-otp/",
        ac_views.ResendActivationOTP.as_view(),
    ),
    path("account/forgot-password/", ac_views.ForgotPassword.as_view()),  # send otp
    path(
        "account/forgot-password-verify-otp/",
        ac_views.VerifyForgotPasswordOTP.as_view(),
    ),  # check otp
    path("account/reset-password/", ac_views.ResetPassword.as_view()),  # reset password
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
    # carrier
    path(
        "sosc/",
        SetOrderStateCarrying.as_view(),
        name="sosc",
    ),
    # customer
    path(
        "soss/",
        SetOrderStateSubmitted.as_view(),
        name="soss",
    ),
    # full search
    path("search/", SearchApiView.as_view(), name="full_search"),
]
