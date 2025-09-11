from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "order"


# Router Setup for
router = DefaultRouter()

router.register(r"user-orders", views.OrderViewSet, basename="user-orders")

urlpatterns = [
    path(
        "user-orders/<int:order_id>/items/",
        views.OrderItemListAPIView.as_view(),
        name="order-item-list",
    ),
    path(
        "user-orders/item-detail/<int:item_id>/",
        views.OrderItemDetailAPIView.as_view(),
        name="order-item-detail",
    ),
    path(
        "user-orders/ar-order/",
        views.AcceptRejectOrderView.as_view(),
    ),
    path(
        "user-orders/re-order/",
        views.ReOrder.as_view(),
    ),
    path("", include(router.urls)),
]
