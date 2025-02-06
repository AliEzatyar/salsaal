from django.urls import include, path
from . import views

app_name = "vendor"

urlpatterns = [
    path("", views.vendor_dashboard, name="vendor_dashboard"),
    path("profile/", views.vendor_profile, name="vendor_profile_edit"),
    path("become-seller/", views.become_seller, name="become_seller"),
    path("register-vendor", views.register_vendor, name="register_vendor"),
    # vendor products CRUD
    path(
        "products/",
        views.vendor_products,
        name="vendor_products",
    ),
    path(
        "catalog-builder/product/add/",
        views.add_product,
        name="add_product",
    ),
    path(
        "catalog-builder/product/<int:id>/edit/",
        views.edit_product,
        name="edit_product",
    ),
    path(
        "catalog-builder/product/<int:id>/delete/",
        views.delete_product,
        name="delete_product",
    ),
    path("dashboard/", views.vendor_dashboard, name="vendor_dashboard"),
    # rating
    path("rate-vendor/<int:vend_id>/", views.rate_vendor, name="rate_vendor"),
]
