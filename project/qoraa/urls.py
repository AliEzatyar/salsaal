from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = "qoraa"

router = DefaultRouter()
router.register(r"qoraas", views.QoraaViewSet, basename="qoraa")

urlpatterns = [
    path("", include(router.urls)),
    path("join-qoraa-vendor/", views.JoinQoraaVendor.as_view(), name="join_qoraa_vendor"),
    path("join/", views.JoinQoraaApiView.as_view(), name="join"),
]
