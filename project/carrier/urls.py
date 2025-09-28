from django.urls import  path
from . import views

app_name = "carrier"


urlpatterns = [
    path("current-order/", views.CarrierOrderApiView.as_view()),
    path("delivered-orders/", views.DeliveredOrdersApiView.as_view()),
    path("run-script/<str:which>/", views.run_script),
]
