from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "order"


# Router Setup for
router = DefaultRouter()

router.register(r"user-orders", views.OrderViewSet, basename="user-orders")

urlpatterns = [
    path("", include(router.urls)),
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
]
