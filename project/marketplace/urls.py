from django.urls import path, include
from marketplace import views

app_name = "marketplace"

urlpatterns = [
    path("", views.marketplace, name="marketplace"),
    path("product-detail/<int:product_id>", views.product_detail, name="product_detail"),
    path("vendors/", views.vendors, name="vendors"),
    path("vendors/<int:page>", views.vendors, name="vendors_by_page"),
    path("search-vendor/", views.vendors, name="search_vendor"),

]
