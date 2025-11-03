from django.urls import path
from . import views

app_name = "qoraa"

urlpatterns = [
    path("current/", views.CurrentQoraaApiView.as_view(), name="current"),
    path("join/", views.JoinQoraaApiView.as_view(), name="join"),
]
