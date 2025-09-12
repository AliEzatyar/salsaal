from locale import strxfrm
from marketplace.models import Category, Discount, FavItem, Food, Rating
from accounts.models import CUSTOMER
from live.models import Notification
from .utils import (
    BestFoodsCounter,
    BestVendorsCounter,
    distance_reach_time,
    distance_to_travel_time,
    haversine_distance as distance_calculator,
)
from marketplace.backends import (
    CustomFoodOrdering,
    CustomFoodSearch,
    CustomVendorOrdering,
    CustomVendorSearch,
    FoodFilterSet,
    VendorFilterSet,
)
from vendor.models import Vendor
from vendor.serializers import (
    VendorSerializerMany,
    AbstractVendorSerializer,
    PublicVendorSerializer,
    VendorSerializerWithFoodImages,
)
from marketplace.serializers import (
    CFoodSerializerDetail,
    CategoryVendorFoodsSerializer,
    CategoryVendorSerializer,
    DiscountedFoodSerializerMany,
    FavItemSerializer,
    FoodSerializerLessDetail,
    FoodSerializerMany,
    RatingSerializer,
    CategorySerializer,
)
from django.db.models import Prefetch
from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, views, viewsets, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from api.permissions import IsHavingFavlist
from django.core.cache import cache
from .utils import BoughtTogetherRecommender
from django.db.models import Avg
import geohash
import h3
from .utils import StandardResultSetPagination, DEFAULT_H3_RESOLUTION, r
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext as _
import time
from django.utils.timezone import datetime

"""Marketplace API Views"""


class MarketplaceViewset(viewsets.ReadOnlyModelViewSet):
    """
    This view  handles representation of foods to normal users.
    For food detail, this view requires user location and city from client app.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FoodSerializerMany
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
        if not city:
            return Food.objects.none()
        city = str(city).lower()
        return Food.objects.filter(
            is_available=True, vendor__user_profile__city=city
        ).select_related("vendor__user_profile")

    @action(detail=True, methods=["get"], url_path="food-item-detail")
    def item_detail(self, request, pk):
        """provides fooditem detail with distance"""
        obj = (
            self.get_object()
        )  # this prompts filter_queryset, city existence is ensured so
        data = request.query_params
        city = self.request.query_params.get("city", None)
        city = str(city).lower()

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
            ser_many = FoodSerializerLessDetail(suggestion_foods, many=True)
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

    def list(self, request, *args, **kwargs):
        # categories
        now = time.time()
        cat_key = "home_categories"
        categories = cache.get(cat_key)
        if not categories:
            # cach miss
            categories = Category.objects.filter(show_on_home=True)
            ser = CategorySerializer(categories, many=True)
            categories = ser.data
            cache.set(cat_key, categories, timeout=24 * 3600)
        # general info
        request_data = request.query_params
        city = request_data.get("city", None)
        location = request_data.get("location", None)
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()
        user_cart_items_count = 0
        user_notf_count = 0
        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
            user_cart_items_count = self.request.user.cart.calculate_total_items()
            user_notf_count = Notification.objects.filter(
                receiver=self.request.user, is_read=False
            ).count()

        except Exception as e:
            print(e)
            return Response(status=400)
        city_vendors_ids = self.get_city_vendors(city)
        city_vendors = (
            Vendor.objects.filter(is_approved=True, id__in=city_vendors_ids)
            .only(
                "id",
                "vendor_name",
                "avg_rating",
                "rating_count",
                "image",
                "logo",
                "vendor_type",
                "user_profile",
                "opening_hours",
            )
            .prefetch_related("opening_hours")
        )
        city_foods = Food.objects.filter(
            is_available=True, vendor__user_profile__city=city
        ).select_related("discount","vendor").only(
            "id",
            "name",
            "image",
            "discount",
            "vendor",
            "min_price",
            "category",
            "likes",
        )

        # discounted foods
        foods_key = f"city:{city}:dis_foods"
        discounted_foods_ids = cache.get(foods_key, None)
        if not discounted_foods_ids:
            discounted_foods_ids = city_foods.filter(
                discount__is_active=True, discount__vendor__user_profile__city=city
            ).values_list("id", flat=True)

            cache.set(foods_key, discounted_foods_ids, 10 * 60)
        discounted_foods_final = city_foods.filter(
            id__in=discounted_foods_ids
        ).select_related("vendor__user_profile")
        distance_reach_time(discounted_foods_final, lat, lon)
        discounted_foods_ser = DiscountedFoodSerializerMany(
            discounted_foods_final, many=True
        )

        # local vendors
        user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
        nearest_h3s = h3.grid_disk(user_h3, 10)
        # filter in db for existing nearby  open city vendors
        local_vendors = city_vendors.filter(
            user_profile__h3_id__in=nearest_h3s,
        ).select_related("user_profile")[:5]
        distance_reach_time(local_vendors, lat, lon, "vendor")
        local_vendors_ser = VendorSerializerMany(local_vendors, many=True)

        # cheapest vendors
        cheapest_vendors = city_vendors.annotate(
            avg_price=Avg("foods__min_price")
        ).order_by("avg_price")
        distance_reach_time(cheapest_vendors, lat, lon, "vendor")
        cheapest_vendors_ser = VendorSerializerMany(cheapest_vendors, many=True)

        # top vendors
        key = f"top_vendors:{city}:city"
        # getting top ratings from cache
        top_vendors = cache.get(key, None)
        if not top_vendors:
            # cache miss
            counter = BestVendorsCounter(city)
            top = counter.read_counts(10)
            top_vendors = city_vendors.filter(id__in=top).order_by("-avg_rating")[:10]
            # adding distance property to each vendor
            distance_reach_time(top_vendors, lat, lon, "vendor")
            top_vendors_ser = VendorSerializerMany(top_vendors, many=True)
            top_vendors = top_vendors_ser.data
            cache.set(key,top_vendors,3600)

        print(time.time() - now, "seconds")
        # final response
        return Response(
            {
                "cart_count": user_cart_items_count,
                "notf_count": user_notf_count,
                "categories": categories,
                "discounted_foods": discounted_foods_ser.data,
                "local_vendors": local_vendors_ser.data,
                "cheapest_vendors": cheapest_vendors_ser.data,
                "top_vendors": top_vendors,
            }
        )

    @action(detail=False, methods=["get"],url_path="home-categories")
    def categories(self, request):
        """this endpoint returns available categories for normal users"""
        cat_key = "home_categories"
        categories = cache.get(cat_key)
        if not categories:
            # cach miss
            categories = Category.objects.filter(show_on_home=True)
            ser = CategorySerializer(categories, many=True)
            categories = ser.data
            cache.set(cat_key, categories, timeout=24 * 3600)
        return Response(categories, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="discounted")
    def discounted_foods(self, request):
        """this endpoint returns discounted foods"""
        request_data = request.query_params
        city = request_data.get("city", None)
        location = request_data.get("location", None)
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()
        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
        except (TypeError, ValueError):
            return Response({"detail": "invalid_location"}, status=400)

        # getting ids of all discounts avaialbe in city from cache
        key = f"discounts:{city}:city"
        foods_key = f"city:{city}:dis_foods"
        all_discounts_in_city = cache.get(key, None)
        discounted_foods_ids = cache.get(foods_key, None)
        if not all_discounts_in_city:
            all_discounts_in_city = Discount.objects.filter(
                is_active=True,
                vendor__user_profile__city=city,
            ).values_list("id", flat=True)
            # print(all_discounts_in_city, "this is discounts ids")
            cache.set(key, all_discounts_in_city, 10 * 60)
            # updating discounted foods
            discounted_foods_ids = Food.objects.filter(
                is_available=True, discount__id__in=all_discounts_in_city
            )
            cache.set(foods_key, discounted_foods_ids, 10 * 60)
        if not discounted_foods_ids:
            discounted_foods_ids = Food.objects.filter(
                is_available=True, discount__id__in=all_discounts_in_city
            )
            cache.set(foods_key, discounted_foods_ids, 10 * 60)
        discounted_foods_final = Food.objects.filter(
            id__in=discounted_foods_ids
        ).select_related("vendor__user_profile")
        try:
            """here can be an error due to long distance of user and vendor,
            since h3 library does not work for a big distance"""
            for f in discounted_foods_final:
                # continue
                distance = round(
                    distance_calculator(
                        f.vendor.user_profile.lattitude,
                        f.vendor.user_profile.longitude,
                        lat,
                        lon,
                    ),
                    1,
                )
                f.distance = distance
                f.reach_time = round(distance_to_travel_time(distance), 1)
        except:
            pass
        # paginating and sending the result
        paginator = StandardResultSetPagination()
        qs = paginator.paginate_queryset(discounted_foods_final, request)
        ser = DiscountedFoodSerializerMany(qs, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["get"], url_path="local-vendors")
    def local_vendors(self, request):
        request_data = request.query_params
        city = request_data.get("city", None)
        location = request_data.get("location", None)
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()

        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
        except (TypeError, ValueError):
            return Response({"detail": "invalid_location"}, status=400)

        city_vendors_ids = self.get_city_vendors(city)
        # finding near areas of the user up to 10 hexagons long -> 3.5km
        user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
        nearest_h3s = h3.grid_disk(user_h3, 10)
        # filter in db for existing nearby  open city vendors
        vendors = Vendor.objects.filter(
            id__in=city_vendors_ids,
            user_profile__h3_id__in=nearest_h3s,
        ).select_related("user_profile")[:5]
        # adding distance property to each vendor
        for vendor in vendors:
            distance = round(
                distance_calculator(
                    vendor.user_profile.lattitude,
                    vendor.user_profile.longitude,
                    lat,
                    lon,
                ),
                1,
            )
            vendor.distance = distance
            vendor.reach_time = round(distance_to_travel_time(distance), 1)

        paginator = StandardResultSetPagination()
        qs = paginator.paginate_queryset(vendors, request)

        ser = VendorSerializerMany(qs, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["get"], url_path="cheapest-vendors")
    def cheapest_vendors(self, request):
        request_data = request.query_params
        city = request_data.get("city", None)
        location = request_data.get("location", None)
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()

        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
        except (TypeError, ValueError):
            return Response({"detail": "invalid_location"}, status=400)
        city_vendors_ids = self.get_city_vendors(city)
        vendors = (
            Vendor.objects.filter(id__in=city_vendors_ids)
            .annotate(avg_price=Avg("foods__min_price"))
            .order_by("avg_price")
        )
        # adding distance property to each vendor
        for vendor in vendors:
            distance = round(
                distance_calculator(
                    vendor.user_profile.lattitude,
                    vendor.user_profile.longitude,
                    lat,
                    lon,
                ),
                1,
            )
            vendor.distance = distance
            vendor.reach_time = round(distance_to_travel_time(distance), 1)
        # paginating and sending the result
        paginator = StandardResultSetPagination()
        qs = paginator.paginate_queryset(vendors, request)
        ser = VendorSerializerMany(qs, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["get"], url_path="top-vendors")
    def top_vendors(self, request):
        """this endpoint returns top rating and most viewed vendors in the city"""
        request_data = request.query_params
        city = request_data.get("city", None)
        location = request_data.get("location", None)
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()

        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
        except (TypeError, ValueError):
            return Response({"detail": "invalid_location"}, status=400)

        key = f"top_vendors:{city}:city"
        # getting top ratings from cache
        top_vendors = cache.get(key, None)
        if not top_vendors:
            # cache miss
            counter = BestVendorsCounter(city)
            top = counter.read_counts(10)
            top_vendors = Vendor.objects.filter(
                is_approved=True, user_profile__city=city, id__in=top
            ).order_by("-avg_rating")[:10]
            # adding distance property to each vendor
            for vendor in top_vendors:
                distance = round(
                    distance_calculator(
                        vendor.user_profile.lattitude,
                        vendor.user_profile.longitude,
                        lat,
                        lon,
                    ),
                    1,
                )
                vendor.distance = distance
                vendor.reach_time = round(distance_to_travel_time(distance), 1)
            # paginating and sending the result
            paginator = StandardResultSetPagination()
            qs = paginator.paginate_queryset(top_vendors, request)
            ser = VendorSerializerMany(qs, many=True)
            if len(top_vendors) > 1:
                cache.set(
                    key,
                    {
                        "count": paginator.page.paginator.count,
                        "next": paginator.get_next_link(),
                        "previous": paginator.get_previous_link(),
                        "results": ser.data,
                    },
                    1 * 3600,
                )
            return paginator.get_paginated_response(ser.data)
        return Response(top_vendors)

    @action(detail=False, methods=["get"],url_name="all_vendors_in_city", url_path="all-vendors-in-city")
    def all_vendors_in_city(self, request):
        """this returns all active vendors in the city"""
        request_data = request.query_params
        city = request_data.get("city", None)

        city = request_data.get("city", None)
        location = request_data.get("location", None)
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()

        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
        except (TypeError, ValueError):
            return Response({"detail": "invalid_location"}, status=400)

        vendors_ids = self.get_city_vendors(city)
        vendors = (
            Vendor.objects.filter(id__in=vendors_ids)
            .prefetch_related(
                Prefetch(
                    "foods",
                    Food.objects.only(
                        "image",
                        "min_price",
                        "name",
                        "rating_count",
                        "avg_rating",
                        "vendor_id",
                    )[:10],
                    to_attr="limited_foods",
                )
            )
            .order_by("-avg_rating")
        )
        for vendor in vendors:
            distance = round(
                distance_calculator(
                    vendor.user_profile.lattitude,
                    vendor.user_profile.longitude,
                    lat,
                    lon,
                ),
                1,
            )
            vendor.distance = distance
            vendor.reach_time = round(distance_to_travel_time(distance), 1)
        # paginating and sending the result
        paginator = StandardResultSetPagination()
        qs = paginator.paginate_queryset(vendors, request)
        ser = VendorSerializerWithFoodImages(qs, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["get"], url_path="nearby-vendors-on-map")
    def nearby_vendors_on_map(self, request):
        """
        this endpoint returns a list of serialized vendors to be shown on map
        it uses AbstractVendorSerializer.
        note: h3.grid_disk returns amount of n-times hexagons away
        as circle from current hex
        """

        request_data = request.query_params
        city = request_data.get("city", None)
        location = request_data.get("location", None)
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()

        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
        except (TypeError, ValueError):
            return Response({"detail": "invalid_location"}, status=400)

        city_vendors_ids = self.get_city_vendors(city)
        # finding near areas of the user up to 10 hexagons long -> 3.5km
        user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
        nearest_h3s = h3.grid_disk(user_h3, 14)
        # filter in db for existing nearby  open city vendors
        vendors = (
            Vendor.objects.filter(
                id__in=city_vendors_ids,
                user_profile__h3_id__in=nearest_h3s,
            )
            .select_related("user_profile")
            .only("vendor_name", "id", "user_profile")
        )
        ser = AbstractVendorSerializer(vendors, many=True)
        return Response(ser.data)

    def get_city_vendors(self, city):
        """this utility method returns ids of city vendors"""
        city = str(city).lower()
        city_vendors = cache.get(f"city:{city}:vendors")

        if not city_vendors:
            # cache miss
            vendors_dict = Vendor.objects.filter(
                is_approved=True, user_profile__city=city
            ).values_list("id", flat=True)
            city_vendors = list(vendors_dict)
            cache.set(f"city:{city}:vendors", city_vendors, 3600 * 1)
        return city_vendors

    """
    # @action(detail=False, methods=["get"], url_path="nearest-fastest")
    # def nearest_fastest_foods(self, request):
    #     `this endpoint returns foods with lowest reach time`
    #     request_data = request.query_params
    #     city = request_data.get("city", None)
    #     location = request_data.get("location", None)
    #     if not city:
    #         return Response({"detail": "provide_a_correct_city"}, status=400)
    #     city = str(city).lower()

    #     if not location:
    #         return Response({"detail": "location_data_needed"}, status=400)
    #     try:
    #         # decoding location
    #         lat, lon = geohash.decode(location)
    #     except (TypeError, ValueError):
    #         return Response({"detail": "invalid_location"}, status=400)

    #     # filtering by only open now
    #     now = timezone.now()
    #     index = now.weekday()
    #     weekday = to_af_weekday(index=index)
    #     now_af = now.astimezone(ZoneInfo("Asia/Kabul")).hour
    #     # getting opening-hour objects from cache or set it
    #     hours_key = f"hours:{now_af}:objects"
    #     hours = cache.get(hours_key)
    #     if not hours:
    #         # cach miss
    #         hours_dict = OpeningHour.objects.filter(
    #             weekday=weekday, start_hour__lte=now_af, end_hour__gt=now_af
    #         ).values_list("id", flat=True)

    #         hours = list(hours_dict)  # [1,2,3,4]
    #         cache.set(hours_key, hours, 3600)

    #     # getting city vendors from cache or setting it
    #     city_vendors = cache.get(f"city:{city}:vendors")
    #     if not city_vendors:
    #         # cache miss
    #         vendors_dict = Vendor.objects.filter(
    #             is_approved=True, user_profile__city=city
    #         ).values_list("id", flat=True)
    #         city_vendors = list(vendors_dict)
    #         cache.set(f"city:{city}:vendors", city_vendors, 3600 * 24)

    #     # finding near areas of the user up to 10 hexagons long
    #     user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
    #     nearest_h3s = h3.grid_disk(user_h3, 10)
    #     foods = Food.objects.filter(
    #         is_available=True,
    #         vendor__id__in=city_vendors,
    #         vendor__opening_hours__in=hours,
    #         vendor__user_profile__h3_id__in=nearest_h3s,
    #     ).select_related("vendor__user_profile")
    #     for food in foods:
    #         distance = h3_distance_to_km(
    #             h3.grid_distance(food.vendor.user_profile.h3_id, user_h3)
    #         )
    #         food.reach_time = round(distance_to_travel_time(distance))
    #         food.distance = round(distance, 1)
    #     # serializing the result
    #     paginator = StandardResultSetPagination()
    #     qs = paginator.paginate_queryset(foods, request)
    #     ser = FoodSerializerMany(qs, many=True)
    #     return paginator.get_paginated_response(ser.data)

    # @action(detail=False, methods=["get"], url_path="week-trending")
    # def week_trending(self, request):
    #     ```this endpoint returns most ordered foods by last week```
    #     request_data = request.query_params
    #     city = request_data.get("city", None)
    #     if not city:
    #         return Response({"detail": "provide_a_correct_city"}, status=400)
    #     city = str(city).lower()

    #     week_ago = timezone.now() - timezone.timedelta(weeks=1)
    #     week_orders_key = f"orders:{city}:week"
    #     # getting last week orders ids from cache
    #     order_ids = cache.get(week_orders_key)
    #     if not order_ids:
    #         # cache miss
    #         order_ids = Order.objects.filter(
    #             user__profile__city=city,
    #             # created_at__gte=week_ago
    #         ).values_list("id", flat=True)
    #         order_ids = [i for i in order_ids]
    #         cache.set(week_orders_key, order_ids, timeout=24 * 3600)
    #     top_week_foods_key = "top_week_foods"
    #     # getting last week orders ids from cache
    #     top_week_foods = cache.get(top_week_foods_key)
    #     result = top_week_foods
    #     if not top_week_foods:
    #         # cache miss
    #         top_week_foods = (
    #             OrderItem.objects.filter(order_id__in=order_ids)
    #             .values("food")  # 'food':id
    #             .annotate(item_count=Count("id"))
    #             .order_by("-item_count")[:10]
    #         )

    #         ids = [x["food"] for x in top_week_foods]
    #         top_week_foods = Food.objects.filter(id__in=ids)
    #         # paginating and sending the result
    #         paginator = StandardResultSetPagination()
    #         qs = paginator.paginate_queryset(top_week_foods, request)
    #         ser = FoodSerializerMany(qs, many=True)
    #         print(ser.data,"to week not in cache")
    #         cache.set(
    #             top_week_foods_key,
    #             {
    #                 "count": paginator.page.paginator.count,
    #                 "next": paginator.get_next_link(),
    #                 "previous": paginator.get_previous_link(),
    #                 "results": ser.data,
    #             },
    #             24 * 3600,
    #         )
    #         return paginator.get_paginated_response(ser.data)
    #     print(result,"top week foods was  in cache")
    #     return Response(result)

    # @action(detail=False, methods=["get"], url_path="best-foods")
    # def best_foods(self, request):
    #     ```this endpoint returns top rating foods in the city```
    #     request_data = request.query_params
    #     city = request_data.get("city", None)
    #     location = request_data.get("location", None)
    #     if not city :
    #         return Response(
    #             {"detail": "provide_a_correct_city"}, status=status.HTTP_400_BAD_REQUEST
    #         )
    #     city = str(city).lower()

    #     if not location:
    #         return Response(
    #             {"detail": "provide_location"}, status=status.HTTP_400_BAD_REQUEST
    #         )
    #     key = f"best_foods:{city}"
    #     best_foods = cache.get(key, None)
    #     if not best_foods:
    #         print("best foods not found in cache")
    #         counter = BestFoodsCounter(city)
    #         most_viewd_ids = counter.read_counts()
    #         best_foods = (
    #             Food.objects.filter(
    #                 is_available=True,
    #                 vendor__user_profile__city=city,
    #                 id__in=most_viewd_ids,
    #             )
    #             .select_related("vendor__user_profile")
    #             .order_by("-avg_rating")[:10]
    #         )
    #         # adding reach time and delivery fee
    #         c_lat, c_lon = geohash.decode(location)

    #         for food in best_foods:
    #             hexagon_distance = h3.grid_distance(
    #                 h3.latlng_to_cell(c_lat, c_lon, DEFAULT_H3_RESOLUTION),
    #                 food.vendor.user_profile.h3_id,
    #             )
    #             food.reach_time = distance_to_travel_time(
    #                 h3_distance_to_km(hexagon_distance)
    #             )
    #         # applying other filters, ordering by distance
    #         # best_foods = self.filter_queryset(best_foods) # distance ordering does not mean...
    #         ser = FoodSerializerMany(best_foods, many=True)
    #         best_foods = ser.data
    #         cache.set(key, best_foods, 1)  # 1 seconds
    #         # ---
    #         # paginating and sending the result
    #         paginator = StandardResultSetPagination()
    #         qs = paginator.paginate_queryset(best_foods, request)
    #         ser = FoodSerializerMany(qs, many=True)
    #         cache.set(
    #             key,
    #             {
    #                 "count": paginator.page.paginator.count,
    #                 "next": paginator.get_next_link(),
    #                 "previous": paginator.get_previous_link(),
    #                 "results": ser.data,
    #             },
    #             1 * 3600,
    #         )
    #         return paginator.get_paginated_response(ser.data)
    #     print("best foods in cache-----")
    #     return Response(best_foods)

    # @action(detail=False, methods=["get"], url_path="recommended")
    # def recommended_foods(self, request):
    #     ```this endpoint returns top rating foods in the city```
    #     request_data = request.query_params
    #     city = request_data.get("city", None)
    #     location = request_data.get("location", None)
    #     if not city :
    #         return Response(
    #             {"detail": "provide_a_correct_city"}, status=status.HTTP_400_BAD_REQUEST
    #         )
    #     city = str(city).lower()

    #     if not location:
    #         return Response(
    #             {"detail": "provide_location"}, status=status.HTTP_400_BAD_REQUEST
    #         )
    #     key = f"best_foods:{city}"
    #     best_foods = cache.get(key, None)
    #     if not best_foods:
    #         print("best foods not found in cache")
    #         counter = BestFoodsCounter(city)
    #         most_viewd_ids = counter.read_counts()
    #         best_foods = (
    #             Food.objects.filter(
    #                 is_available=True,
    #                 vendor__user_profile__city=city,
    #                 id__in=most_viewd_ids,
    #             )
    #             .select_related("vendor__user_profile")
    #             .order_by("-avg_rating")[:10]
    #         )
    #         # adding reach time and delivery fee
    #         c_lat, c_lon = geohash.decode(location)

    #         for food in best_foods:
    #             hexagon_distance = h3.grid_distance(
    #                 h3.latlng_to_cell(c_lat, c_lon, DEFAULT_H3_RESOLUTION),
    #                 food.vendor.user_profile.h3_id,
    #             )
    #             food.reach_time = distance_to_travel_time(
    #                 h3_distance_to_km(hexagon_distance)
    #             )
    #         # applying other filters, ordering by distance
    #         # best_foods = self.filter_queryset(best_foods) # distance ordering does not mean...
    #         ser = FoodSerializerMany(best_foods, many=True)
    #         best_foods = ser.data
    #         cache.set(key, best_foods, 1)  # 1 seconds
    #         # ---
    #         # paginating and sending the result
    #         paginator = StandardResultSetPagination()
    #         qs = paginator.paginate_queryset(best_foods, request)
    #         ser = FoodSerializerMany(qs, many=True)
    #         cache.set(
    #             key,
    #             {
    #                 "count": paginator.page.paginator.count,
    #                 "next": paginator.get_next_link(),
    #                 "previous": paginator.get_previous_link(),
    #                 "results": ser.data,
    #             },
    #             1 * 3600,
    #         )
    #         return paginator.get_paginated_response(ser.data)
    #     print("best foods in cache-----")
    #     return Response(best_foods)

    # @action(detail=False, methods=["get"], url_path="cheapest")
    # def cheapest_foods(self, request):
    #     request_data = request.query_params
    #     city = request_data.get("city", None)
    #     location = request_data.get("location", None)
    #     if not city :
    #         return Response({"detail": "provide_a_correct_city"}, status=400)
    #     city = str(city).lower()

    #     if not location:
    #         return Response({"detail": "location_data_needed"}, status=400)
    #     try:
    #         # decoding location
    #         lat, lon = geohash.decode(location)
    #     except (TypeError, ValueError):
    #         return Response({"detail": "invalid_location"}, status=400)

    #     foods = Food.objects.filter(
    #         vendor__user_profile__city=city, is_available=True
    #     ).order_by("min_price")
    #     # paginating and sending the result
    #     paginator = StandardResultSetPagination()
    #     qs = paginator.paginate_queryset(foods, request)
    #     ser = FoodSerializerMany(qs, many=True)
    #     return paginator.get_paginated_response(ser.data)
"""


class FoodSearchViewset(viewsets.ReadOnlyModelViewSet):
    """
    this viewset enables a user search for a fooditem
    the result is filtered by the user's city.
    """

    serializer_class = FoodSerializerMany
    queryset = Food.objects.filter(is_available=True)
    # django-filter
    filter_backends = [
        CustomFoodSearch,
        DjangoFilterBackend,
        CustomFoodOrdering,
    ]
    # filering
    filterset_class = FoodFilterSet

    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class LikeFood(views.APIView):

    def get(self, *args, **kwargs):
        data = self.request.query_params
        food_id = data.get("id", None)
        if not food_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        exists = Food.objects.filter(id=food_id).exists()
        if exists:
            key = f"food:{food_id}:likes"
            r.incrby(key, 1)
            return Response()
        return Response(status=status.HTTP_404_NOT_FOUND)


class LikeVendor(views.APIView):

    def get(self, *args, **kwargs):
        data = self.request.query_params
        vendor_id = data.get("id", None)
        if not vendor_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        exists = Vendor.objects.filter(id=vendor_id).exists()
        if exists:
            key = f"vendor:{vendor_id}:likes"
            r.incrby(key, 1)
            return Response()
        return Response(status=status.HTTP_404_NOT_FOUND)


class VendorSearchViewset(viewsets.ReadOnlyModelViewSet):
    """
    this viewset enables a user to search for a vendor
    result is filtered by both city and max_distance, so lat and long is need too.
    """

    queryset = Vendor.objects.filter(is_approved=True)
    serializer_class = VendorSerializerMany
    pagination_class = StandardResultSetPagination
    permission_classes = [AllowAny]
    # django-filter, note that put ordering at the end since ordering matters in this list if you override two above
    filter_backends = [
        CustomVendorSearch,
        DjangoFilterBackend,
        CustomVendorOrdering,
    ]
    # filering
    filterset_class = VendorFilterSet


class RatingViewSet(viewsets.ModelViewSet):
    http_method_names = ["get", "post", "delete", "patch"]
    serializer_class = RatingSerializer
    pagination_class = StandardResultSetPagination
    # order of ratings
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]

    def get_queryset(self):
        """returns rating objects of a related object [food, vendor, carrier]"""
        object_id = self.request.query_params.get("obj_id", None)
        # user should be logged in and own the rating object
        if self.request.method in ("DELETE", "PATCH"):
            if (
                not self.request.user.is_authenticated
                or self.request.user.role != CUSTOMER
            ):
                return Rating.objects.none()
            return Rating.objects.filter(user=self.request.user)
        # for GET
        if not object_id:
            return Rating.objects.none()
        try:
            ct = ContentType.objects.get_for_model(Vendor)
            query_set = Rating.objects.filter(
                content_type=ct, object_id=int(object_id), enabled=True
            ).order_by("-rating")
            return query_set
        except:
            # if any problem, no rating is returned
            return Rating.objects.none()

    def create(self, request, *args, **kwargs):
        """overriden, obj_id, type"""
        if self.request.user.role != CUSTOMER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        data = request.data
        obj_id = data.get("obj_id")
        liked_foods = data.get("liked_foods", None)
        rating_data = data.get("rating")
        if not obj_id or not type(obj_id) == int:
            return Response(
                {"detail": "provide_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        previous = Rating.objects.filter(
            object_id=int(obj_id), user=request.user
        ).first()
        # handling likes of food
        if liked_foods:
            for f in liked_foods:
                try:
                    print("food like...")
                    food = Food.objects.get(id=f)
                    food.likes += 1
                    food.save()
                except:
                    pass
        # handling update
        if previous:
            # prviously exists, performing update
            previous.comment = rating_data["comment"]
            previous.rating = rating_data["rating"]
            previous.enabled = True
            previous.save()
            return Response(status=status.HTTP_200_OK)
        # new rating
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
            ct = ContentType.objects.get_for_model(Vendor)
            instance.content_type = ct
            related_obj = Vendor.objects.filter(id=obj_id).first()
            if not related_obj:
                return Response(
                    {"detail": "no_such_vendor"}, status=status.HTTP_400_BAD_REQUEST
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
        return f"vdr:{id}:dt"

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
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()

        if not user_location:
            return Response({"detail": "no_location_provided"}, status=400)
        if vendor_id:
            try:
                # ------------------------ getting vendor details either cache or db
                v_lon, v_lon = None, None
                ser_data = None
                vendor_in_cache = cache.get(self.vendor_detail_key(vendor_id))
                lat, lon = geohash.decode(user_location)

                if vendor_in_cache:
                    ser_data = vendor_in_cache.copy()
                else:
                    obj = Vendor.objects.filter(
                        is_approved=True, id=vendor_id, user_profile__city=city
                    ).first()
                    if obj:
                        vendor_foods = Food.objects.filter(
                            vendor_id=obj.id, is_available=True
                        )
                        featured_items = vendor_foods.filter(is_featured=True)
                        vendor_categories = sorted(
                            list(
                                set(
                                    vendor_foods.values_list(
                                        "category__name", flat=True
                                    )
                                )
                            ),
                            key=lambda x: strxfrm(x),
                            reverse=True,
                        )
                        distance = round(
                            distance_calculator(
                                obj.user_profile.lattitude,
                                obj.user_profile.longitude,
                                lat,
                                lon,
                            ),
                            1,
                        )
                        discounted_vendor_foods = vendor_foods.filter(
                            discount__is_active=True
                        ).only("id", "name", "image", "min_price", "category")
                        obj.featured_items = featured_items  # later on we decide
                        obj.discounted_foods = discounted_vendor_foods
                        obj.categories = vendor_categories
                        obj.categories_count = len(vendor_categories)
                        obj.distance = distance
                        obj.reach_time = distance_to_travel_time(distance)
                        ser = PublicVendorSerializer(obj)
                        ser_data = ser.data
                        cache.set(
                            self.vendor_detail_key(vendor_id), ser_data, 5 * 60
                        )  # cache for 10 minutes

                    else:
                        return Response(status=status.HTTP_404_NOT_FOUND)

                # ------------------- increasing vendor view count
                counter = BestVendorsCounter(str(city))
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


class ListVendorFoods(views.APIView):
    """
    THis returns foods of a vendor either sorted by min price
    or by grouped by category
    """

    def get(self, *args, **kwargs):
        data = self.request.query_params
        vendor_id = data.get("vendor_id", None)
        cheapest = data.get("cheapest", None)
        if not vendor_id:
            return Response(
                {"detail": "no_vendor_id"}, status=status.HTTP_400_BAD_REQUEST
            )
        if cheapest:
            cheap_foods = Food.objects.filter(
                vendor_id=vendor_id, is_available=True, is_drink=False
            ).order_by("min_price")[:10]
            ser = FoodSerializerLessDetail(cheap_foods, many=True)
            return Response(ser.data)
        try:
            # checking the cache
            key = self.get_cache_key(vendor_id)
            data = cache.get(key, None)
            if not data:
                categories = (
                    Category.objects.filter(foods__vendor_id=vendor_id)
                    .distinct()
                    .prefetch_related(
                        Prefetch(
                            "foods",
                            Food.objects.filter(vendor_id=vendor_id, is_available=True),
                        )
                    )
                    .order_by("-name")
                )
                ser = CategoryVendorFoodsSerializer(categories, many=True)
                data = ser.data
                cache.set(key, data, 5 * 60)  # cache for 5 minutes
            return Response(data)
        except Exception as e:
            print("error occured in vendor list", e)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def get_cache_key(self, vendor_id):
        return f"vendor:{vendor_id}:foods"


class FoodsByCategory(generics.ListAPIView):
    """THis returns foods by category, also pagintaes the result"""

    serializer_class = CategoryVendorSerializer
    pagination_class = StandardResultSetPagination

    def get_queryset(self):
        """filtering by category"""
        data = self.request.query_params
        category_id = data.get("category_id", None)
        user_location = data.get("location", None)
        city = data.get("city", None)
        if not (category_id and user_location and city):
            return Vendor.objects.none()
        city = str(city).lower()
        vendors = (
            Vendor.objects.filter(
                foods__category_id=category_id,
                is_approved=True,
                user_profile__city=city,
            )
            .distinct()
            .prefetch_related(
                Prefetch("foods", queryset=Food.objects.filter(category_id=category_id))
            )
            .select_related("user_profile")
            .only("vendor_name", "avg_rating", "foods", "user_profile")
        )
        # adding reach time and distance to each vendor
        lat, lon = geohash.decode(user_location)
        for vendor in vendors:
            distance = round(
                distance_calculator(
                    vendor.user_profile.lattitude,
                    vendor.user_profile.longitude,
                    lat,
                    lon,
                ),
                1,
            )
            vendor.distance = distance
            vendor.reach_time = round(distance_to_travel_time(distance), 0)
        return vendors

