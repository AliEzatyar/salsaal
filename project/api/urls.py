from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import AppInfoAPIView

# importing urls
# Router Setup for
router = DefaultRouter()

app_name = "api"

urlpatterns = [
    path("cart/", include("cart.urls", namespace="cart")),
    path("account/", include("accounts.urls", namespace="accounts")),
    path("carrier/", include("carrier.urls", namespace="carrier")),
    path("marketplace/", include("marketplace.urls", namespace="marketplace")),
    path("order/", include("order.urls", namespace="order")),
    path("vendor/", include("vendor.urls", namespace="vendor")),
    path("live/", include("live.urls", namespace="live")),
    path("qoraa/", include("qoraa.urls", namespace="qoraa")),
    path("payment/",include("payment.urls",namespace="payment")),
    path("app/info/",AppInfoAPIView.as_view(), name="app-info"),
    path("api/app/info/",AppInfoAPIView.as_view(), name="app-info"),   
]
