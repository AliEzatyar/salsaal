from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "carrier"

# Router Setup for
router = DefaultRouter()

# managing carriers as vendor
router.register(
    r"manage-carriers", views.ManageCarrierViewSet, basename="manage-carriers"
)
# see orders as vendor
router.register(
    r"carrier-orders", views.CarrierOrdersApiView, basename="carrier-orders"
)


urlpatterns = [
    path(
        "add-carrier/",
        views.AddCarrierAPIView.as_view(),
    ),
    path(
        "set-order-state-delivered/",
        views.SetOrderStateDelivered.as_view(),
    ),
    path(
        "set-order-state-carrying/",
        views.SetOrderStateCarrying.as_view(),
    ),
    path("", include(router.urls)),
]
