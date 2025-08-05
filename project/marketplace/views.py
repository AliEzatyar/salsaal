from zoneinfo import ZoneInfo
from marketplace.models import Category, FavItem, Food, Rating
from order.models import Order, OrderItem
from accounts.models import CUSTOMER
from multiVend.settings.base import DEFAULT_SEARCH_DISTANCE
from vendor.utils import to_af_weekday
from .utils import (
    BestFoodsCounter,
    BestVendorsCounter,
    haversine_distance as distance_calculator,
)
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
import geohash

"""Marketplace API Views"""


class MarketplaceViewset(viewsets.ReadOnlyModelViewSet):
    """
    This view  handles representation of foods to normal users.
    For food detail, this view requires user location and city from client app.
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
        """
        only available foods in the user's city
        """

        city = self.request.query_params.get("city", None)
        if not city or not city in settings.CITY_NAMES:
            return Food.objects.none()
        return Food.objects.filter(
            is_available=True, vendor__user_profile__city=city
        ).select_related("vendor__user_profile")

    def get_object(self):
        obj = super().get_object()
        if not obj.vendor.is_approved:
            return None
        return obj

    def filter_queryset(self, queryset, *args, **kwargs):
        """
        overriden to apply ordering the result by distance
        some of the bellow action views may call it in the end.
        """
        lat = kwargs.get("lat")
        lon = kwargs.get("lon")
        for backend in list(self.filter_backends):
            queryset = backend().filter_queryset(self.request, queryset, self)
        # ordering by distance/reach-time
        queryset = sorted(
            queryset,
            key=lambda x: distance_calculator(
                x.vendor.user_profile.lattitude,
                x.vendor.user_profile.longitude,
                lat,
                lon,
            ),
        )
        return queryset

    @method_decorator(cache_page(5 * 60))
    def list(self, request, *args, **kwargs):
        """its called last"""
        return super().list(request, *args, **kwargs)

    @action(detail=True, methods=["get"], url_path="food-item-detail")
    def item_detail(self, request, pk):
        """provides fooditem detail with distance"""
        obj = (
            self.get_object()
        )  # this prompts filter_queryset, city existence is ensured so
        data = request.query_params
        city = self.request.query_params.get("city", None)
        location = data.get("location", None)
        vendor_profile = obj.vendor.user_profile
        try:
            # decoding location data
            lat, lon = geohash.decode(location)
            distance = distance_calculator(
                float(vendor_profile.lattitude),
                float(vendor_profile.longitude),
                float(lat),
                float(lon),
            )
            # serializer for the item
            serializer = CFoodSerializerDetail(instance=obj)
            # listing and serializing recommended foods
            recommender = BoughtTogetherRecommender()
            suggestion_ids = recommender.suggest_foods_for([obj.id])
            suggestion_foods = Food.objects.filter(id__in=suggestion_ids)
            ser_many = FoodSerializerMany(suggestion_foods, many=True)
            # updating the counter for this food
            counter = BestFoodsCounter(city)
            counter.update_counts(obj.id)
            # sending the response
            return Response(
                {
                    "item": serializer.data,
                    "distance": distance,
                    "suggestions": ser_many.data,
                }
            )
        except Exception as e:
            return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], url_path="home-categories")
    def categories(self, request):
        """this endpoint returns available categories for normal users"""
        cat_key = "home_categories"
        categories = cache.get(cat_key)
        if not categories:
            # cach miss
            categories = Category.objects.filter(show_on_home=True).values("name", "id")
            ser = CategorySerializer(categories, many=True)
            categories = ser.data
            cache.set(cat_key, categories, timeout=24 * 3600)
        return Response(categories, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="nearby-vendors")
    def nearby_vendors(self, request):
        """this endpoint returns nearby_vendors"""
        request_data = request.query_params
        city = request_data.get("city", None)
        location = request_data.get("location")
        max_distance = request_data.get("max_distance", DEFAULT_SEARCH_DISTANCE)  # km
        try:
            max_distance = float(max_distance)
        except:
            max_distance = DEFAULT_SEARCH_DISTANCE

        if not city or not city in settings.CITY_NAMES:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
            user_location = Point(float(lon), float(lat), srid=4326)
        except (TypeError, ValueError):
            return Response({"detail": "invalid_location"}, status=400)

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
            .order_by("distance")[:10]
        )

        # pagination
        page = self.paginate_queryset(vendors)
        if page:
            ser = VendorSerializerMany(page, many=True, context={"request": request})
            return self.get_paginated_response(ser.data)
        ser = VendorSerializerMany(vendors, many=True, context={"request": request})
        return Response(ser.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="week-trending")
    def week_trending(self, request):
        """this endpoint returns most ordered foods by last week"""
        request_data = request.query_params
        city = request_data.get("city", None)
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

    @action(detail=False, methods=["get"], url_path="top-vendors")
    def top_vendors(self, request):
        """this endpoint returns top rating and most viewed vendors in the city"""
        request_data = request.query_params
        city = request_data.get("city", None)
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
                is_approved=True, user_profile__city=city, id__in=top
            ).order_by("-avg_rating")[:10]
            ser = VendorSerializerMany(top_vendors, many=True)
            top_vendors = ser.data
            cache.set(key, top_vendors, 1 * 3600)  # 1 day
        return Response(top_vendors)

    @action(detail=False, methods=["get"], url_path="best-foods")
    def best_foods(self, request):
        """this endpoint returns top rating foods in the city"""
        request_data = request.query_params
        city = request_data.get("city", None)
        if not city or not city in settings.CITY_NAMES:
            return Response(
                {"detail": "provide_a_correct_city"}, status=status.HTTP_400_BAD_REQUEST
            )
        key = f"best_foods:{city}"
        best_foods = cache.get(key, None)
        if not best_foods:
            counter = BestFoodsCounter(city)
            most_viewd_ids = counter.read_counts()
            best_foods = Food.objects.filter(
                is_available=True,
                vendor__user_profile__city=city,
                id__in=most_viewd_ids,
            ).order_by("-avg_rating")[:10]
            # applying filters
            best_foods = self.filter_queryset(best_foods)
            ser = FoodSerializerMany(best_foods, many=True)
            best_foods = ser.data
            cache.set(key, best_foods, 1 * 3600)  # 1 day

        return Response(best_foods)

    @action(detail=False, methods=["get"], url_path="recommended")
    def recommended_foods(self, request):
        pass

    @action(detail=False, methods=["get"], url_path="discounted")
    def discounted_foods(self, request):
        pass


class FoodSearchViewset(viewsets.ReadOnlyModelViewSet):
    """
    this viewset enables a user search for a fooditem
    the result is filtered by the user's city.
    """

    serializer_class = FoodSerializerMany
    queryset = Food.objects.filter(is_available=True)
    permission_classes = [AllowAny]
    # django-filter
    filter_backends = [
        CustomFoodSearch,
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    ordering_fields = ["name", "min_price", "avg_rating"]
    ordering = ["-avg_rating"]
    # filering
    filterset_class = FoodFilterSet

    def filter_queryset(self, queryset):
        """overriden to apply city   filtering on overall search and filter"""
        city = self.request.query_params.get("city", None)
        if not city or not city in settings.CITY_NAMES:
            return queryset.none()
        for backend in list(self.filter_backends):
            queryset = backend().filter_queryset(self.request, queryset, self)
        return queryset.filter(vendor__user_profile__city=city)


class VendorSearchViewset(viewsets.ReadOnlyModelViewSet):
    """
    this viewset enables a user to search for a vendor
    result is filtered by both city and max_distance, so lat and long is need too.
    """

    queryset = Vendor.objects.filter(is_approved=True)

    serializer_class = VendorSerializerMany
    permission_classes = [AllowAny]
    # django-filter, note that put ordering at the end since ordering matters in this list if you override two above
    filter_backends = [
        CustomVendorSearch,
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    ordering_fields = ["vendor_name", "avg_rating", "rating_count"]
    ordering = ["-avg_rating"]
    # filering
    filterset_class = VendorFilterSet

    def filter_queryset(self, queryset):
        """overriden to apply city filtering on overall search and filter"""
        city = self.request.query_params.get("city", None)
        if not city or not city in settings.CITY_NAMES:
            return queryset.none()
        for backend in list(self.filter_backends):
            queryset = backend().filter_queryset(self.request, queryset, self)
        return queryset.filter(user_profile__city=city)


class RatingViewSet(viewsets.ModelViewSet):
    permission_classes = [NotAdmin]
    http_method_names = ["get", "post", "delete", "patch"]
    serializer_class = RatingSerializer
    # order of ratings
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]

    def get_queryset(self):
        """returns rating objects of a related object [food, vendor, carrier]"""
        object_id = self.request.query_params.get("obj_id", None)
        rating_type = self.request.query_params.get("type", None)
        max_results = self.request.query_params.get("max", None)
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
            max_results = int(max_results)
            if max_results and max_results > 0:
                query_set = Rating.objects.filter(
                    content_type=ct, object_id=int(object_id), enabled=True
                ).order_by("-rating")[:max_results]
            else:
                query_set = Rating.objects.filter(
                    content_type=ct, object_id=int(object_id), enabled=True
                ).order_by("-rating")
            return query_set
        except:
            # if any problem, no rating is returned
            return Rating.objects.none()

    def create(self, request, *args, **kwargs):
        """overriden, obj_id, type"""
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


class CategoriesReadAPIView(views.APIView):
    """This endpoint a list of categories for vendors when adding new fooditems"""

    http_method_names = ["get"]

    def get(self, *args, **kwargs):
        return Response(
            {"categories": [(cat.id, cat.name) for cat in Category.objects.all()]}
        )


class PublicVendorDetail(views.APIView):
    """this view enables a normal user see a vendor detail with its fooditems avaialble"""

    serializer_class = PublicVendorSerializer
    permission_classes = [AllowAny]
    queryset = Vendor.objects.filter(is_approved=True)

    def vendor_detail_key(self, id):
        return f"vendor:{id}:details"

    def vendor_location_key(self, id):
        return f"vendor:{id}:location"

    def get(self, *args, **kwargs):
        """
        This initially tries to get vendor details from cache, if not found,
        then queries db and serialize and cache.
        we have to use caching since its not only about vendor but its menue.
        """
        request_data = self.request.query_params
        vendor_id = request_data.get("id", None)
        city = request_data.get("city", None)
        user_location = request_data.get("location", None)
        # take info from user profile if authentication, realtime location prompt should be
        if not city or not city in settings.CITY_NAMES:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        if not user_location:
            return Response({"detail": "no_location_provided"}, status=400)
        if vendor_id:
            try:
                # ------------------------ getting vendor details either cache or db
                v_lon, v_lon = None, None
                ser_data = None
                vendor_in_cache = cache.get(self.vendor_detail_key(vendor_id))
                if vendor_in_cache:
                    ser_data = vendor_in_cache.copy()
                    location = ser_data["location"]
                    v_lat = location[0]
                    v_lon = location[1]
                else:
                    obj = Vendor.objects.filter(
                        is_approved=True, id=vendor_id, user_profile__city=city
                    ).first()
                    if obj:
                        ser = PublicVendorSerializer(obj)
                        ser_data = ser.data.copy()
                        cache.set(
                            self.vendor_detail_key(vendor_id), ser_data, 10 * 60
                        )  # cache for 10 minutes
                        v_lat = ser_data["location"][0]
                        v_lon = ser_data["location"][1]

                    else:
                        return Response(status=status.HTTP_404_NOT_FOUND)
                # decoding location and calculating distance
                c_lat, c_lon = geohash.decode(user_location)
                distance = distance_calculator(
                    lat1=v_lat,
                    lon1=v_lon,
                    lat2=c_lat,
                    lon2=c_lon,
                )
                ser_data["distance"] = distance
                # ------------------- increasing vendor view count
                counter = BestVendorsCounter(str(city).title())
                counter.update_counts(vendor_id)
                return Response(ser_data, status=status.HTTP_200_OK)
            except Exception as e:
                print("error occured in vendor detail", e, e.args)
                return Response(status=status.HTTP_501_NOT_IMPLEMENTED)
        else:
            return Response(
                {"detail": "no_id_provided"}, status=status.HTTP_400_BAD_REQUEST
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
