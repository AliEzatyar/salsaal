from django.urls import path, include
from order import views

app_name = "order"

urlpatterns = [
    path("", views.create_order, name="create_order"),
    path("my-orders",views.list_orders,name="customer_orders"),
]
