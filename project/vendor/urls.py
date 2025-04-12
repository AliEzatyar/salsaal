from django.urls import include, path
from . import views

app_name = "vendor"

urlpatterns = [
    path("", views.vendor_dashboard, name="vendor_dashboard"),
    path("profile/", views.vendor_profile, name="vendor_profile_edit"),
    # this is just for normal users
    path("vendor-details/<str:vendor_name>/",views.vendor_details,name="vendor_details"),
    path("become-seller/", views.become_seller, name="become_seller"),
    path("register-vendor", views.register_vendor, name="register_vendor"),
    # vendor foods CRUD
    path(
        "foods/",
        views.vendor_foods,
        name="vendor_foods",
    ),
    path(
        "catalog-builder/food/add/",
        views.add_food,
        name="add_food",
    ),
    path(
        "catalog-builder/food/<int:id>/edit/",
        views.edit_food,
        name="edit_food",
    ),
    path(
        "catalog-builder/food/<int:id>/delete/",
        views.delete_food,
        name="delete_food",
    ),
    # path("dashboard/", views.vendor_dashboard, name="vendor_dashboard"),
    # rating
]
