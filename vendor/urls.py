from django.urls import include, path
from . import views

app_name = "vendor"

urlpatterns = [
    path("", views.vend_dashboard, name="vendor_dashboard"),
    path("profile/", views.vendor_profile, name="vendor_profile_edit"),
    path("catalog-builder/", views.catalog_builder, name="catalog_builder"),
    path("products-list/<int:cat_id>/", views.products_by_category, name="products_by_category"),
    path("dashboard/", views.vend_dashboard, name="vendor_dashboard"),
]
