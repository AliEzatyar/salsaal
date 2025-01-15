from django.urls import include, path
from . import views

app_name = 'accounts'

urlpatterns = [
    path("register-resturant", views.register_rest, name="reg_res"),
    path("register", views.register_user, name="reg_user"),
]
