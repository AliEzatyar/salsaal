from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "order"


# Router Setup for
router = DefaultRouter()

router.register(r"user-orders", views.OrderViewSet, basename="user-orders")

urlpatterns = [
    path(
        "user-orders/ar-order/",
        views.AcceptRejectOrderView.as_view(),
    ),
    path(
        "user-orders/re-order/",
        views.ReOrder.as_view(),
    ),
    path(
        "set-order-state-delivered/",
        views.SetOrderStateDelivered.as_view(),
    ),
    path("", include(router.urls)),
]
