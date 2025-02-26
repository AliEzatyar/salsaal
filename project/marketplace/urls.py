from django.urls import path, include
from marketplace import views

app_name = "marketplace"

urlpatterns = [
    path("", views.marketplace, name="marketplace"),
    path("product-search/",views.marketplace,name="product_search"),
    path("product-detail/<int:product_id>", views.product_detail, name="product_detail"),
    path("vendors/", views. vendors, name="vendors"),
    path("rate",views.rate, name="rate")
]
