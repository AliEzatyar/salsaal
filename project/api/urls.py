from django.urls import include, path
from . import views
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.routers import DefaultRouter
from order.views import OrderViewSet, OrderItemListAPIView, OrderItemDetailAPIView
from marketplace.views import RatingViewSet, MarketplaceViewset, SearchApiView
from vendor.views import ConvertToVendorAPIView, ListVendorOrders, VendorFoodsManageViewSet, VendorAPIView
from carrier.views import AddCarrierAPIView, CarrierOrdersApiView, ManageCarrierViewSet, SetOrderStateCarrying, SetOrderStateSubmitted
from cart.views import CartApiView
from marketplace.views import CategoriesReadAPIView
from accounts import views as ac_views

# Router Setup for
router = DefaultRouter()
# order viewset routing
router.register(r"orders", OrderViewSet,basename="orders")
# user profile
router.register(r"user-profile", ac_views.UserProfileViewset,basename="user-profile")
# user detail
router.register(r"user-detail", ac_views.UserViewset,basename="user-detail")

# rating viewset routing
router.register(r"ratings", RatingViewSet,basename="rating")
# food managemet routing
router.register(r"vendor-foods", VendorFoodsManageViewSet, basename="vendor-foods")
# managing carriers as vendor
router.register(r"manage-carriers", ManageCarrierViewSet,basename="manage-carriers")
# see orders as vendor
router.register(r"vendor-orders", ListVendorOrders, basename="vendor-orders")
# router seeing order
router.register(r"carrier-orders", CarrierOrdersApiView, basename="carrier-orders")
# food retrive  routing
router.register(r"home", MarketplaceViewset,basename="home")

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
    ),
    path(
        "convert-to-vendor/",
        ConvertToVendorAPIView.as_view(),
    ),
    path(
        "add-carrier/",
        AddCarrierAPIView.as_view(),
    ),
    # get categories
    path("get-category-names/", CategoriesReadAPIView.as_view()),
    # carrier
    path(
        "sosc/",
        SetOrderStateCarrying.as_view(),
    ),
    # customer
    path(
        "soss/",
        SetOrderStateSubmitted.as_view(),
    ),
    # full search
    path("search/", SearchApiView.as_view(), name="full_search"),
]
