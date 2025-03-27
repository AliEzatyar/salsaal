from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import OrderItemDetailAPIView, OrderItemListAPIView, OrderViewSet

# Router Setup for order model
order_router = DefaultRouter()
order_router.register(r"orders", OrderViewSet)


urls = [
    path("", include(order_router.urls)),
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
]
