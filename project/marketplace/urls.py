from django.urls import path, include
from marketplace import views

app_name = "marketplace"

urlpatterns = [
    path("vendors/", views.vendors, name="vendors"),
    path("vendors/<int:page>", views.vendors, name="vendors_by_page"),
    path("search-vendor/",views.vendors,name="search_vendor")
]
