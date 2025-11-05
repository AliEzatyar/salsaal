from django.urls import path
from . import views

app_name = "qoraa"

urlpatterns = [
    path("join-qoraa-vendor/", views.JoinQoraaVendor.as_view(), name="join_qoraa_vendor"),
    path("current/", views.CurrentQoraaApiView.as_view(), name="current"),
    path("join/", views.JoinQoraaApiView.as_view(), name="join"),
]
