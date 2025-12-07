from django.urls import path
from . import views

app_name = "qoraa"


urlpatterns = [
    path("", views.ListQoraaApiView.as_view(), name="list-qoraas"),
    path("join/", views.JoinQoraaApiView.as_view(), name="join"),
] 
