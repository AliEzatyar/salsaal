from django.urls import include, path
from . import views
app_name = "vendor"

urlpatterns = [
    path("",views.vend_dashboard,name="vendor_dashboard"),
    path("profile/", views.vendor_profile, name="vendor_profile"),
    path("dashboard/", views.vend_dashboard, name="vendor_dashboard"),
]
