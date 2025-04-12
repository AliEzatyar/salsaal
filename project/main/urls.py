from django.urls import path
from . import views
app_name = "main"

urlpatterns = [
    path("favorites/", views.favlist, name="favlist"),
    path(
        "add-item-to-favorites/<int:food_id>",
        views.add_to_favlist,
        name="add_to_favlist",
    ),
    path(
        "delete-item-favorite-item/<int:item_id>",
        views.delete_from_favlist,
        name="delete_fav_item",
    ),
    path("", views.home, name="home"),
    path("<str:cat>/", views.home, name="home_category"),
]
