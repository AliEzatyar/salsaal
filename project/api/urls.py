from django.urls import include, path
from rest_framework.routers import DefaultRouter

# importing urls
# Router Setup for
router = DefaultRouter()

app_name = "api"

urlpatterns = [
    path("account/", include("accounts.urls", namespace="accounts")),
    path("carrier/", include("carrier.urls", namespace="carrier")),
    path("cart/", include("cart.urls", namespace="cart")),
    path("marketplace/", include("marketplace.urls", namespace="marketplace")),
    path("order/", include("order.urls", namespace="order")),
    path("vendor/", include("vendor.urls", namespace="vendor")),
    path("live/", include("live.urls", namespace="live")),
]
