from django.urls import path, include
from marketplace import views

app_name = "marketplace"

urlpatterns = [
    path("all-vendors", views.vendors, name="all_vendors"),
    path("vendors/<int:page>", views.vendors, name="vendors_by_page"),
    path(
        "vendors-by-category/<slug:category_slug>",
        views.vendors,
        name="vendors_by_category",
    ),
    path("vendors-by-rating/<int:rating>", views.vendors, name="vendors_by_rating"),
    path("vendors-by-city/<str:city>", views.vendors, name="vendors_by_city"),
]
