from django.urls import include, path
from . import views

app_name = "vendor"

urlpatterns = [
    path("", views.vendor_dashboard, name="vendor_dashboard"),
    path("vendor-details/<str:vendor_name>/",views.vendor_details,name="vendor_details"),
]
