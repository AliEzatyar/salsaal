from django.urls import path
from . import views

app_name = "cart"


urlpatterns = [
    # cart
    path(
        "",
        views.CartApiView.as_view(),  # Endpoint for managing cart operations
        name="cart-detail",
    ),
]
