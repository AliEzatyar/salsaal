from django.urls import path, include
from marketplace import views

app_name = "marketplace"

urlpatterns = [
    path("", views.marketplace, name="marketplace"),
    path("food-search/",views.marketplace,name="food_search"),
    path("food-detail/<int:food_id>", views.food_detail, name="food_detail"),
    path("vendors/", views. vendors, name="vendors"),
]
