from django.urls import path, include
from . import views

app_name = "cart"

urlpatterns = [
    path("items", views.show_cart, name="cart"),
    path(
        "add/<int:food_id>",
        views.add_to_cart,
        name="add_to_cart",
    ),
    path("edit", views.edit_cart, name="edit_cart"),
    path(
        "delete/<int:item_id>",
        views.delete_cart_item,
        name="delete_cart_item",
    ),
]
