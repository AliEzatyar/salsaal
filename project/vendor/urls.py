from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "vendor"


# Router Setup for
router = DefaultRouter()

router.register(
    r"vendor-foods", views.VendorFoodsManageViewSet, basename="vendor-foods"
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
    path(
        "ar-order/",
        views.AcceptRejectOrderView.as_view(),
    ),
    path(
        "convert-to-vendor/",
        views.ConvertToVendorAPIView.as_view(),
    ),
    path("vendor-revenue/", views.VendorRevenueView.as_view()),
    path("", include(router.urls)),
]
