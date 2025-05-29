from zoneinfo import ZoneInfo
from marketplace.models import Category, FavItem, Food, Rating
from order.models import Order, OrderItem
from accounts.models import CUSTOMER
from vendor.utils import to_af_weekday
from .utils import BestVendorsCounter, haversine_distance as distance_calculator
from api.backends import (
    CustomFoodSearch,
    CustomVendorSearch,
    FoodFilterSet,
    VendorFilterSet,
)
from vendor.models import OpeningHour, Vendor
from vendor.serializers import VendorSerializerMany
from marketplace.serializers import (
    CFoodSerializerDetail,
    FavItemSerializer,
    FoodSerializerMany,
    PublicVendorSerializer,
    RatingSerializer,
    CategorySerializer,
)
from carrier.models import Carrier

from django.db.models.aggregates import Count
from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.utils import timezone
from rest_framework import filters, status, views, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from api.permissions import IsHavingFavlist, NotAdmin
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from .utils import BoughtTogetherRecommender
from django.conf import settings
"""Marketplace API Views"""


class MarketplaceViewset(viewsets.ReadOnlyModelViewSet):
    """
                    Home Page
    This view  handles representation of foods to normal users.
    For food detail, this view requires user location saved on profile instance. if user is not
    auhtenticated, query params 'lat' and 'lon' must be sent.
    """

    serializer_class = FoodSerializerMany
    permission_classes = [AllowAny]

    # django-filter
    filter_backends = [
        filters.OrderingFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "min_price", "avg_rating"]
    ordering = ["-avg_rating"]
    # filering
    filterset_class = FoodFilterSet

    def get_queryset(self):
        return Food.objects.filter(is_available=True)

    def get_object(self):
        obj = super().get_object()
        if not obj.vendor.is_approved:
            return None
        return obj

    @method_decorator(cache_page(5 * 60))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="food-item-detail")
    def item_detail(self, request, pk):
        """provides fooditem detail with distance"""
        obj = self.get_object()
        data = request.query_params
        lat = data.get("lat", None)
        lon = data.get("lon", None)
        vendor_profile = obj.vendor.user_profile
        try:
            distance = distance_calculator(
                float(vendor_profile.lattitude),
                float(vendor_profile.longitude),
                float(lat),
                float(lon),
            )
            serializer = CFoodSerializerDetail(instance=obj)
            # recommended foods
            recommender = BoughtTogetherRecommender()
            suggestion_ids = recommender.suggest_foods_for([obj.id])
            suggestion_foods = Food.objects.filter(id__in=suggestion_ids)
            ser_many = FoodSerializerMany(suggestion_foods, many=True)
            return Response(
                {
                    "item": serializer.data,
                    "distance": distance,
                    "suggestions": ser_many.data,
                }
            )
        except Exception as e:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], url_path="all-categories")
    def categories(self, request):
        """this endpoint returns available categories"""
        cat_key = "home_categories"
        categories = cache.get(cat_key)
        if not categories:
            # cach miss
            categories = Category.objects.filter(show_on_home=True).values("name", "id")
            ser = CategorySerializer(categories, many=True)
            categories = ser.data
            cache.set(cat_key, categories, timeout=24 * 3600)
        return Response(categories, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="nearby-vendor")
    def nearby_vendors(self, request):
        """this endpoint returns nearby_vendors"""
        city = request.data.get("city", None)
        lat = request.data.get("lat", None)
        lon = request.data.get("lon", None)
        max_distance = request.data.get("max_distance", 10)  # km
        try:
            max_distance = float(max_distance)
        except:
            max_distance = 10

        if not city or not city in settings.CITY_NAMES:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        if not lat or not lon:
            return Response(
                {"detail": "Latitude and longitude are required."}, status=400
            )
        try:
            user_location = Point(float(lon), float(lat), srid=4326)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid coordinates."}, status=400)
        user_location = Point(float(lon), float(lat), srid=4326)

        # filtering by only open now
        now = timezone.now()
        index = now.weekday()
        weekday = to_af_weekday(index=index)
        now_af = now.astimezone(ZoneInfo("Asia/Kabul")).hour
        # getting opening-hour objects from cache
        hours_key = f"hours:{now_af}:objects"
        hours = cache.get(hours_key)
        if not hours:
            # cach miss
            hours_dict = OpeningHour.objects.filter(
                weekday=weekday, start_hour__lte=now_af, end_hour__gt=now_af
            ).values_list("id", flat=True)
            hours = list(hours_dict)  # [1,2,3,4]
            cache.set(hours_key, hours, 3600)

        # getting city vendors from cache
        city_vendors = cache.get(f"city:{city}:vendors")
        if not city_vendors:
            # cache miss
            vendors_dict = Vendor.objects.filter(
                is_approved=True, user_profile__city=city
            ).values_list("id", flat=True)
            city_vendors = list(vendors_dict)
            cache.set(f"city:{city}:vendors", city_vendors, 3600 * 24)

        # final filter in db
        vendors = (
            Vendor.objects.filter(id__in=city_vendors, opening_hours__in=hours)
            .annotate(distance=Distance("user_profile__location", user_location))
            .filter(distance__lte=D(km=max_distance))
            .order_by("distance")[:5]
        )

        # pagination
        page = self.paginate_queryset(vendors)
        if page:
            ser = VendorSerializerMany(page, many=True, context={"request": request})
            return self.get_paginated_response(ser.data)
        ser = VendorSerializerMany(vendors, many=True, context={"request": request})
        return Response(ser.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="week-trending")
    def week_trending(self, request):
        """this endpoint returns most ordered foods by last week"""
        city = request.data.get("city", None)
        if request.user.is_authenticated:
            city = request.user.city
        if not city or not city in settings.CITY_NAMES:
            return Response({"detail": "provide_a_correct_city"}, status=400)

        week_ago = timezone.now() - timezone.timedelta(weeks=1)
        week_orders_key = f"orders:{city}:week"
        # getting last week orders ids from cache
        order_ids = cache.get(week_orders_key)
        if not order_ids:
            # cache miss
            order_ids = Order.objects.filter(
                user__profile__city=city, created_at__gte=week_ago
            ).values_list("id", flat=True)
            order_ids = [i for i in order_ids]
            cache.set(week_orders_key, order_ids, timeout=24 * 3600)

        top_week_foods_key = "top_week_foods"
        # getting last week orders ids from cache
        top_week_foods = cache.get(top_week_foods_key)
        if not top_week_foods:
            # cache miss
            top_week_foods = (
                OrderItem.objects.filter(order_id__in=order_ids)
                .values("food")  # 'food':id
                .annotate(item_count=Count("id"))
                .order_by("-item_count")[:10]
            )

            ids = [x["food"] for x in top_week_foods]
            top_week_foods = Food.objects.filter(id__in=ids)
            ser = FoodSerializerMany(top_week_foods, many=True)
            result = ser.data
            cache.set(top_week_foods_key, result, 24 * 3600)

        return Response(result)

    @action(detail=False, methods=["post"], url_path="top-vendors")
    def top_vendors(self, request):
        """this endpoint returns top rating and most viewed vendors in the city"""
        city = request.data.get("city", None)
        if not city or not city in settings.CITY_NAMES:
            return Response(
                {"detail": "provide_a_correct_city"}, status=status.HTTP_400_BAD_REQUEST
            )
        city = str(city).title()
        key = f"top_vendors:{city}"
        # getting top ratings from cache
        top_vendors = cache.get(key, None)
        if not top_vendors:
            # cache miss
            counter = BestVendorsCounter(city)
            top = counter.read_counts(10)
            top_vendors = Vendor.objects.filter(
                is_approved=True,
                user_profile__city=city,
                id__in=top
            ).order_by("-avg_rating")[:10]
            ser = VendorSerializerMany(top_vendors, many=True)
            top_vendors = ser.data
            cache.set(key, top_vendors, 1 * 3600)  # 1 days
        return Response(top_vendors)

    @action(detail=False, methods=["post"], url_path="top-rating-foods")
    def top_rating_foods(self, request):
        """this endpoint returns top rating foods in the city"""
        city = request.data.get("city", None)
        if not city or not city in settings.CITY_NAMES:
            return Response(
                {"detail": "provide_a_correct_city"}, status=status.HTTP_400_BAD_REQUEST
            )
        city = str(city).title()
        key = f"top_foods:{city}"
        top_foods = cache.get(key, None)
        if not top_foods:
            top_foods = Food.objects.filter(
                is_available=True,
                vendor__user_profile__city=city,
            ).order_by("-avg_rating")[:10]
            ser = FoodSerializerMany(top_foods, many=True)
            top_foods = ser.data
            cache.set(key, top_foods, 1 * 3600 * 24)  # 3 days

        return Response(top_foods)


# depricated
class SearchApiView(views.APIView):
    """This api view handles searching for both food and vendor objects considering distance"""

    permission_classes = [AllowAny]

    def get(self, *args, **kwargs):
        query = self.request.query_params.get("query", None)
        lon = self.request.query_params.get("lon", None)
        lat = self.request.query_params.get("lat", None)
        max_distance = self.request.query_params.get("max_distance", 5)
        user_location = None
        # determinig user location
        try:
            if lat and lon:
                user_location = Point(float(lon), float(lat), srid=4326)
            else:
                user_location = self.request.user.profile.location
        except:
            Response(
                {"error": "invalid location data"}, status=status.HTTP_400_BAD_REQUEST
            )

        # handling empty query
        if not query or not query.strip():
            return Response(
                {"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        if not user_location:
            return Response(
                {"error": "no_user_location"}, status=status.HTTP_400_BAD_REQUEST
            )

        # search for foods
        foods = Food.objects.filter(
            name__icontains=query, is_available=True
        ).select_related("vendor__user_profile")
        foods = foods.annotate(
            distance=Distance("vendor__user_profile__location", user_location)
        )
        # limiting distance
        foods = foods.filter(distance__lte=D(km=max_distance))
        foods_serializer = FoodSerializerMany(foods, many=True)

        # vendors found by query and limiting distance
        vendors = (
            Vendor.objects.filter(vendor_name__icontains=query, is_approved=True)
            .annotate(distance=Distance("user_profile__location", user_location))
            .filter(distance__lte=D(km=max_distance))
        )
        # preparing as json
        vendors_serializer = VendorSerializerMany(vendors, many=True)
        total_found = len(vendors) + len(foods)
        # success
        return Response(
            {
                "total": total_found,
                "foods": foods_serializer.data,
                "vendors": vendors_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class FoodSearchViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = FoodSerializerMany

    queryset = Food.objects.filter(is_available=True)
    permission_classes = [AllowAny]
    # django-filter
    filter_backends = [
        filters.OrderingFilter,
        CustomFoodSearch,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "min_price", "avg_rating"]
    ordering = ["-avg_rating"]
    # filering
    filterset_class = FoodFilterSet


class VendorSearchViewset(viewsets.ReadOnlyModelViewSet):
    serializer_class = VendorSerializerMany
    queryset = Vendor.objects.filter(is_approved=True)
    permission_classes = [AllowAny]
    # django-filter
    filter_backends = [
        filters.OrderingFilter,
        CustomVendorSearch,
        DjangoFilterBackend,
    ]
    ordering_fields = ["vendor_name", "avg_rating", "rating_count"]
    ordering = ["-avg_rating"]
    # filering
    filterset_class = VendorFilterSet


class RatingViewSet(viewsets.ModelViewSet):
    permission_classes = [NotAdmin]
    http_method_names = ["get", "post", "delete", "patch"]
    serializer_class = RatingSerializer
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]

    def get_queryset(self):
        """returns rating objects of a related object [food, vendor, carrier]"""
        object_id = self.request.query_params.get("obj_id", None)
        rating_type = self.request.query_params.get("type", None)
        rating_limit = self.request.query_params.get("rating_limit", None)
        # user should be logged in and own the rating object
        if self.request.method in ("DELETE", "PATCH"):
            if (
                not self.request.user.is_authenticated
                or self.request.user.role != CUSTOMER
            ):
                return Rating.objects.none()
            return Rating.objects.filter(user=self.request.user)
        # for GET
        if not object_id or not rating_type:
            return Rating.objects.none()
        try:
            if rating_type == "vendor":
                ct = ContentType.objects.get_for_model(Vendor)
            elif rating_type == "food":
                ct = ContentType.objects.get_for_model(Food)
            elif rating_type == "carrier":
                ct = ContentType.objects.get_for_model(Carrier)
            else:
                return Rating.objects.none()
            rating_limit = int(rating_limit)
            if rating_limit and rating_limit > 0:
                query_set = Rating.objects.filter(
                    content_type=ct, object_id=int(object_id), enabled=True
                ).order_by("-rating")[:rating_limit]
            else:
                query_set = Rating.objects.filter(
                    content_type=ct, object_id=int(object_id), enabled=True
                ).order_by("-rating")
            return query_set
        except:
            # if any problem, no rating is returned
            return Rating.objects.none()

    def create(self, request, *args, **kwargs):
        """overriden, obj_id, type,"""
        if not self.request.user.is_authenticated or self.request.user.role != CUSTOMER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        data = request.data
        rating_type = data.get("type")
        obj_id = data.get("obj_id")
        rating_data = data.get("rating")
        if not rating_type or not obj_id or not type(obj_id) == int:
            return Response(
                {"error": "rating type must be sent"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        previous = Rating.objects.filter(
            object_id=int(obj_id), user=request.user
        ).first()
        # handling indirect update
        if previous:
            # prviously exists, performing update
            previous.comment = rating_data["comment"]
            previous.enabled = True
            previous.save()
            return Response({"updated": True}, status=status.HTTP_200_OK)
        else:
            # performing new rating creation
            serializer = self.get_serializer(data=rating_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(
                serializer
            )  # sets instance to serializer after creation
            instance = serializer.instance
            #
            related_obj = None

            if rating_type == "vendor":
                ct = ContentType.objects.get_for_model(Vendor)
                instance.content_type = ct
                related_obj = Vendor.objects.filter(id=obj_id).first()
            elif rating_type == "food":
                ct = ContentType.objects.get_for_model(Food)
                instance.content_type = ct
                related_obj = Food.objects.filter(id=obj_id).first()
            elif rating_type == "carrier":
                ct = ContentType.objects.get_for_model(Carrier)
                instance.content_type = ct
                related_obj = Carrier.objects.filter(id=obj_id).first()

            if not related_obj:
                return Response(
                    {"error": "no such object"}, status=status.HTTP_400_BAD_REQUEST
                )

            instance.object_id = int(obj_id)
            instance.save()
            related_obj.update_avg_rating()
            # successfull creation
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        """setting user manually from request context"""
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """updating obj rating avg and count if one of its ratings is deleted"""
        rating = self.get_object()
        obj = rating.related_obj
        rating.delete()
        obj.update_avg_rating()
        return Response(status=status.HTTP_204_NO_CONTENT)


# categories for vendor
class CategoriesReadAPIView(views.APIView):
    http_method_names = ["get"]

    def get(self, *args, **kwargs):
        return Response(
            {
                "categories": [
                    (cat.id, cat.name)
                    for cat in Category.objects.filter(show_on_home=True)
                ]
            }
        )


class PublicVendorDetail(views.APIView):
    """this view enables a normal user see a vendor detail with its menue"""

    serializer_class = PublicVendorSerializer
    permission_classes = [AllowAny]
    queryset = Vendor.objects.filter(is_approved=True)

    def post(self, *args, **kwargs):
        request = self.request
        obj_id = request.data.get("id", None)
        city = request.data.get("city", None)
        lat = request.data.get("lat", None)
        lon = request.data.get("lon", None)
        # take info from user profile if authentication, realtime location prompt should be
        if not city or not city in settings.CITY_NAMES:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        if not lat or not lon:
            return Response(
                {"detail": "Latitude and longitude are required."}, status=400
            )
        if obj_id:
            try:
                obj = Vendor.objects.filter(is_approved=True, id=obj_id,user_profile__city=city).first()
                ser = PublicVendorSerializer(obj)
                if obj:
                    distance = distance_calculator(
                        lat1=obj.user_profile.lattitude,
                        lon1=obj.user_profile.longitude,
                        lat2=lat,
                        lon2=lon,
                    )
                    data = ser.data.copy()
                    data["distance"] = distance
                    # increasing vendor view count
                    counter = BestVendorsCounter(str(city).title())
                    counter.update_counts(obj.id)

                    return Response(data, status=status.HTTP_200_OK)
                else:
                    return Response(status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                print(e.args,e)
                return Response(status=status.HTTP_501_NOT_IMPLEMENTED)
        else:
            return Response(
                {"detail": "no_id_sent"}, status=status.HTTP_400_BAD_REQUEST
            )


class FavListViewset(viewsets.ModelViewSet):
    """THis viewset handles CRUD of Fav List"""

    serializer_class = FavItemSerializer
    permission_classes = [IsAuthenticated, IsHavingFavlist]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["favlist"] = self.request.user.favlist.id
        return context

    def get_queryset(self):
        return FavItem.objects.filter(favlist=self.request.user.favlist)
