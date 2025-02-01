from django.urls import include, path
from . import views

app_name = "vendor"

urlpatterns = [
    path("", views.vendor_dashboard, name="vendor_dashboard"),
    path("become-seller/", views.become_seller, name="become_seller"),
    path("register-vendor", views.register_vendor, name="register_vendor"),
    path("profile/", views.vendor_profile, name="vendor_profile_edit"),
    path("catalog-builder/", views.catalog_builder, name="catalog_builder"),
    # catalog CRUD
    path(
        "products/",
        views.vendor_products,
        name="vendor_products",
    ),
    path(
        "catalog-builder/category/add/",
        views.add_category,
        name="add_category",
    ),
    path(
        "catalog-builder/category/<int:id>/edit/",
        views.edit_category,
        name="edit_category",
    ),
    path(
        "catalog-builder/category/<int:id>/delete/",
        views.delete_category,
        name="delete_category",
    ),
    # product CRUD
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
    # dashboard
    path("dashboard/", views.vendor_dashboard, name="vendor_dashboard"),
    # rating
    path("rate-vendor/<int:vend_id>/", views.rate_vendor, name="rate_vendor"),
]
