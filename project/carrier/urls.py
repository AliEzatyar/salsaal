from django.urls import  path
from . import views

app_name = "carrier"


urlpatterns = [
    path("current-order/", views.CarrierOrderApiView.as_view(), name="current-order"),  # Endpoint for viewing the current order of a carrier
    path("delivered-orders/", views.DeliveredOrdersApiView.as_view(), name="delivered-orders"),  # Endpoint for viewing delivered orders
]
