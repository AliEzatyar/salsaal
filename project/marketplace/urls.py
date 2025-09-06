from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = "marketplace"

# Router Setup for
router = DefaultRouter()

router.register(r"home", views.MarketplaceViewset, basename="home")

router.register(r"f-search", views.FoodSearchViewset, basename="food-search")

router.register(r"v-search", views.VendorSearchViewset, basename="vendor-search")

router.register(r"ratings", views.RatingViewSet, basename="rating")

router.register(r"fav-list", views.FavListViewset, basename="fav-list")


urlpatterns = [
    path("", include(router.urls)),
    # get categories
    path("get-category-names/", views.CategoriesReadAPIView.as_view()),
    path("public-vendor-detail/", views.PublicVendorDetail.as_view()),
    path("get-vendor-foods/", views.ListVendorFoods.as_view()),
    path("foods-by-category/", views.FoodsByCategory.as_view()),
    path("like-food-item/", views.LikeFood.as_view()),
    path("like-vendor/", views.LikeVendor.as_view()),
    path(
        "ar-order/",
        views.AcceptRejectOrderView.as_view(),
    ),
    # full search
]
    
