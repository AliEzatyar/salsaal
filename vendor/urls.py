from django.urls import include, path
from . import views

app_name = "vendor"

urlpatterns = [
    path("", views.vend_dashboard, name="vendor_dashboard"),
    path("profile/", views.vendor_profile, name="vendor_profile_edit"),
    path("catalog-builder/", views.catalog_builder, name="catalog_builder"),
    # catalog CRUD
    path(
        "catalog-builder/category/<int:cat_id>/",
        views.products_by_category,
        name="products_by_category",
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
    path("dashboard/", views.vend_dashboard, name="vendor_dashboard"),
    # rating
    path("rate-vendor/<int:vend_id>/",views.rate_vendor,name="rate_vendor"),
]
