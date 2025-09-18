from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "carrier"



urlpatterns = [
    path("my-order/", views.CarrierOrderApiView.as_view() ),
    path("run-script/<str:which>/",views.run_script)
]
