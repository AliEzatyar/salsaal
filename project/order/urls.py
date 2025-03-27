from django.urls import path, include
from order import views
from .api.urls import urls
app_name = "order"

urlpatterns = [
    path("", views.create_order, name="create_order"),
    path("my-orders", views.list_orders, name="customer_orders"),
    path("cancel-order", views.cancel_order, name="cancel_order"),
    # API
    path("api/",include(urls))
]
