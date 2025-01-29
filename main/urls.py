from django.urls import path
from .views import home
app_name = "main"

urlpatterns = [
    path("", home, name="home"),
    path("<str:cat>/", home, name="home_category"),
]
