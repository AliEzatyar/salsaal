from django.urls import include, path
from rest_framework.routers import DefaultRouter

from carrier.views import SetOrderStateCarrying
from . import views

app_name = "vendor"


# Router Setup for
router = DefaultRouter()

router.register(
    r"vendor-foods", views.VendorFoodsManageViewSet, basename="vendor-foods"
)
router.register(
    r"manage-discount", views.ManageDiscountViewSet, basename="manage-discount"
)
# managing carriers as vendor
router.register(
    r"manage-carriers", views.ManageCarrierViewSet, basename="manage-carriers"
)
router.register(
    r"manage-opening-hours", views.ManageOpeningHours, basename="manage-opening-hours"
)
router.register(r"vendor-orders", views.ListVendorOrders, basename="vendor-orders")
# food retrive  routing

urlpatterns = [
    # vendor
    path(
        "vendor-details/",
        views.VendorAPIView.as_view(),
    ),
    # path(
    #     "ar-order/",
    #     # views.AcceptRejectOrderView.as_view(),
    # ),
    path(
        "convert-to-vendor/",
        views.ConvertToVendorAPIView.as_view(),
    ),
    path("vendor-revenue/", views.VendorRevenueView.as_view()),
    path(
        "add-carrier/",
        views.AddCarrierAPIView.as_view(),
    ),
    path(
        "carriers-now/",
        views.CarriersNow.as_view(),
    ),
    path(
        "estimate-order-time/",
        views.CalculateOrderTimeAndDeliveryCost.as_view(),
    ),
    path(
        "set-order-state-carrying/",
        SetOrderStateCarrying.as_view(),
    ),
    path("", include(router.urls)),
]
