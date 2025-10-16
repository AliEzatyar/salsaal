from locale import strxfrm
from marketplace.models import Category, Discount, FavItem, Food, Rating
from accounts.models import CUSTOMER
from live.models import Notification
from .utils import (
    BestFoodsCounter,
    BestVendorsCounter,
    distance_reach_time,
    distance_to_travel_time,
    haversine_distance 
)
from marketplace.backends import (
    CustomFoodOrdering,
    CustomFoodSearch,
    CustomVendorOrdering,
    CustomVendorSearch,
    FoodFilterSet,
    VendorFilterSet,
)
from vendor.models import Promotion, Vendor
from vendor.serializers import (
    PromotionSerializer,
    VendorSerializerMany,
    AbstractVendorSerializer,
    PublicVendorSerializer,
    VendorSerializerWithFoodImages,
)
from marketplace.serializers import (
    CVFoodSerializerDetail,
    CategoryVendorFoodsSerializer,
    CategoryVendorSerializer,
    DiscountedFoodSerializerMany,
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
from django.core.cache import cache
from .utils import BoughtTogetherRecommender
from django.db.models import Avg
import geohash
import h3
from .utils import StandardResultSetPagination, DEFAULT_H3_RESOLUTION, r
from rest_framework.permissions import IsAuthenticated
from django.utils.translation import gettext as _
import time
from django.db.models import Count, Window, F
from django.db.models.functions import RowNumber
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
            is_available=True, vendor__city=city
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
        vendor = obj.vendor
        try:
            # decoding location data

            lat, lon = geohash.decode(location)
            distance = haversine_distance(
                float(vendor.latitude),
                float(vendor.longitude),
                float(lat),
                float(lon),
            )
            # serializer for the item
            serializer = CVFoodSerializerDetail(instance=obj)
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
            cache.set(cat_key, categories, timeout=10 * 60)
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
            try:
                lat, lon = geohash.decode(location)
            except:
                # try getting from user's profile, if user has signed in
                lat = float(request.user.profile.latitude)
                lon = float(request.user.profile.longitude)
                city = request.user.profile.city
                if not (lat and lon):
                    # sign up without locaiton data
                    return Response(
                        {
                            "cart_count": 0,
                            "notf_count": 0,
                            "categories": None,
                            "promotions": None,
                            "discounted_foods": None,
                            "local_vendors": None,
                            "cheapest_vendors": None,
                            "top_vendors": None,
                        }
                    )
            user_cart_items_count = self.request.user.cart.calculate_total_items()
            user_notf_count = Notification.objects.filter(
                receiver=self.request.user, is_read=False
            ).count()

        except Exception as e:
            print("error", e)
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
        city_foods = (
            Food.objects.filter(is_available=True, vendor__city=city)
            .select_related("discount", "vendor")
            .only(
                "id",
                "name",
                "image",
                "discount",
                "vendor",
                "min_price",
                "category",
                "likes",
            )
        )
        # promotions
        promotions = Promotion.objects.filter(city=city)
        promotion_serializer = PromotionSerializer(promotions, many=True)
        # discounted foods
        dis_foods_key = f"city:{city}:dis_foods"
        discounted_foods_ids = cache.get(dis_foods_key, None)
        if not discounted_foods_ids:
            discounted_foods_ids = city_foods.filter(
                discount__is_active=True, 
            ).values_list("id", flat=True)

            cache.set(dis_foods_key, discounted_foods_ids, 10 * 60)
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
            h3_id__in=nearest_h3s,
        ).select_related("user_profile")[:10]
        distance_reach_time(local_vendors, lat, lon, "vendor")
        local_vendors_ser = VendorSerializerMany(local_vendors, many=True)

        # cheapest vendors
        cheapest_vendors = city_vendors.annotate(
            avg_price=Avg("foods__min_price")
        ).order_by("avg_price")[:10]
        distance_reach_time(cheapest_vendors, lat, lon, "vendor")
        cheapest_vendors_ser = VendorSerializerMany(cheapest_vendors, many=True)

        # top vendors
        counter = BestVendorsCounter(city)
        top = counter.read_counts(10)        
        top_vendors = city_vendors.filter(id__in=top).order_by("-avg_rating")[:10]
        # adding distance property to each vendor
        distance_reach_time(top_vendors, lat, lon, "vendor")
        top_vendors_ser = VendorSerializerMany(top_vendors, many=True)
        top_vendors = top_vendors_ser.data
        print(time.time() - now, "seconds")
        # final response
        return Response(
            {
                "cart_count": user_cart_items_count,
                "notf_count": user_notf_count,
                "categories": categories,
                "promotions": promotion_serializer.data,
                "discounted_foods": discounted_foods_ser.data,
                "local_vendors": local_vendors_ser.data,
                "cheapest_vendors": cheapest_vendors_ser.data,
                "top_vendors": top_vendors,
            }
        )

    @action(detail=False, methods=["get"], url_path="home-categories")
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
                vendor__city=city,
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
                    haversine_distance(
                        f.vendor.latitude,
                        f.vendor.longitude,
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
            h3_id__in=nearest_h3s,
        ).select_related("user_profile")[:10]
        # adding distance property to each vendor
        for vendor in vendors:
            distance = round(
                haversine_distance(
                    vendor.latitude,
                    vendor.longitude,
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
            .order_by("avg_price")[:10]
        )
        # adding distance property to each vendor
        for vendor in vendors:
            distance = round(
                haversine_distance(
                    vendor.latitude,
                    vendor.longitude,
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

        counter = BestVendorsCounter(city)
        top = counter.read_counts(10)
        top_vendors = Vendor.objects.filter(
            is_approved=True, city=city, id__in=top
        ).order_by("-avg_rating")[:10]
        distance_reach_time(top_vendors,lat,lon,"vendor")
        # paginating and sending the result
        paginator = StandardResultSetPagination(10)
        qs = paginator.paginate_queryset(top_vendors, request)
        ser = VendorSerializerMany(qs, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(
        detail=False,
        methods=["get"],
        url_name="all_vendors_in_city",
        url_path="all-vendors-in-city",
    )
    def all_vendors_in_city(self, request):
        """this returns all active vendors in the city"""
        request_data = request.query_params
        city = request_data.get("city", None)

        city = request_data.get("city", None)
        location = request_data.get("location", None)
        if not city:
            return Response({"detail": "provide_a_correct_city"}, status=400)
        city = str(city).lower()
        print("request ot all vendors.....")
        if not location:
            return Response({"detail": "location_data_needed"}, status=400)
        try:
            # decoding location
            lat, lon = geohash.decode(location)
        except (TypeError, ValueError):
            return Response({"detail": "invalid_location"}, status=400)
        vendors_ids = self.get_city_vendors(city)
        # foods limited to 3 IMPORTANT FOR PERFORMANCE
        foods_with_limit = (
            Food.objects.annotate(
                rn=Window(
                    expression=RowNumber(),
                    partition_by=[F("vendor_id")],
                    order_by=F("avg_rating").desc(),
                )
            )
            .filter(rn__lte=3)  # limit to 3 foods per vendor
            .only("id", "vendor_id", "name", "image", "min_price", "rating_count", "avg_rating")
        )
        vendors = (
            Vendor.objects.filter(id__in=vendors_ids)
            .prefetch_related(
                Prefetch(
                    "foods",
                    foods_with_limit,
                )
            )
            .order_by("-avg_rating")
        )
        for vendor in vendors:
            distance = round(
                haversine_distance(
                    vendor.latitude,
                    vendor.longitude,
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

        try:
            # decoding location
            lat, lon = geohash.decode(location)
        except:
            lat = float(request.user.profile.latitude)
            lon = float(request.user.profile.longitude)
            city = request.user.profile.city
        now = time.time()
        city_vendors_ids = self.get_city_vendors(city)
        # finding near areas of the user up to 10 hexagons long -> 3.5km
        user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
        nearest_h3s = h3.grid_disk(user_h3, 20)
        # filter in db for existing nearby  open city vendors
        vendors = (
            Vendor.objects.filter(
                id__in=city_vendors_ids,
                h3_id__in=nearest_h3s,
            )
            .select_related("user_profile")
            .only("vendor_name", "id", "user_profile")
        )
        ser = AbstractVendorSerializer(vendors, many=True)
        print(time.time()-now," seconds")
        return Response(ser.data)

    def get_city_vendors(self, city):
        """this utility method returns ids of city vendors"""
        city = str(city).lower()
        city_vendors = cache.get(f"city:{city}:vendors")

        if not city_vendors:
            # cache miss
            vendors_dict = Vendor.objects.filter(
                is_approved=True, city=city
            ).values_list("id", flat=True)
            city_vendors = list(vendors_dict)
            cache.set(f"city:{city}:vendors", city_vendors, 3600 * 1)
        return city_vendors


class FoodSearchViewset(viewsets.ReadOnlyModelViewSet):
    """
    this viewset enables a user search for a fooditem
    the result is filtered by the user's city.
    """
    pagination_class = StandardResultSetPagination
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
        print("rating for ", object_id)
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

    @action(detail=False, methods=["get"], url_path="vendor-ratings-initial")
    def rating_initial(self, *args, **kwargs):
        """this returns vendor ratings first-part"""
        object_id = self.request.query_params.get("obj_id", None)
        qs = self.get_queryset()
        vendor_name = None
        # print(object_id)
        if object_id:

            vendor = Vendor.objects.filter(id=object_id).only("vendor_name").first()
            if vendor:
                vendor_name = vendor.vendor_name

        ratings = (
            qs.values("rating").annotate(num_rating=Count("id")).order_by("-rating")
        )
        total_ratings = qs.count()
        avg_rating = qs.aggregate(average_rating=Avg("rating"))["average_rating"]
        total_reviews = qs.exclude(comment=None).count()
        star_percentages = {
            rating["rating"]: (rating["num_rating"] / total_ratings) * 100
            for rating in ratings
        }
        # print(total_ratings, total_reviews, star_percentages)
        return Response(
            {
                "vendor_name": vendor_name,
                "total_ratings": total_ratings,
                "total_reviews": total_reviews,
                "average_rating": avg_rating,
                "star_percentages": star_percentages,
            }
        )

    def create(self, request, *args, **kwargs):
        """overriden, obj_id, type"""
        if self.request.user.role != CUSTOMER:
            return Response(status=status.HTTP_403_FORBIDDEN)
        data = request.data
        obj_id = data.get("obj_id")
        liked_foods = data.get("liked_foods", None)
        rating_data = data.get("rating")
        print(data)
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
                    food = Food.objects.get(id=f)
                    food.likes += 1
                    food.save()
                except Exception as e:
                    print("error in liking foods...", e)
                    pass
        # handling update
        if previous:
            print("rating already existed...")
            # prviously exists, performing update
            ser = self.get_serializer(previous, data=rating_data)
            ser.is_valid(raise_exception=True)
            ser.save()
            ser.instance.related_obj.update_avg_rating()
            print("rating updated,,,,", ser.instance)
            return Response(status=status.HTTP_200_OK)
        # new rating
        else:
            print("new rating....")
            # performing new rating creation
            serializer = self.get_serializer(data=rating_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(
                serializer
            )  # sets instance to serializer after creation
            print(
                "rating created",
            )
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
        print(user_location,"locaiton in vendor detail")
        if not user_location:
            return Response({"detail": "no_location_provided"}, status=400)
        if vendor_id:
            try:
                # ------------------------ getting vendor details either cache or db
                ser_data = None
                vendor_in_cache = cache.get(self.vendor_detail_key(vendor_id))
                lat, lon = geohash.decode(user_location)
                vendor = Vendor.objects.get(
                    is_approved=True, id=vendor_id,city=city
                )
                # vendor is in cache
                if vendor_in_cache:
                    ser_data = vendor_in_cache.copy()
                # vendor not in cache
                else:
                    if vendor:
                        vendor_foods = Food.objects.filter(
                            vendor_id=vendor.id, is_available=True
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

                        discounted_vendor_foods = vendor_foods.filter(
                            discount__is_active=True
                        ).only("id", "name", "image", "min_price", "category")
                        vendor.featured_items = featured_items  # later on we decide
                        vendor.discounted_foods = discounted_vendor_foods
                        vendor.categories = vendor_categories
                        vendor.categories_count = len(vendor_categories)
                        ser = PublicVendorSerializer(vendor)
                        ser_data = ser.data
                        cache.set(
                            self.vendor_detail_key(vendor_id), ser_data, 5 * 60
                        )  # cache for 10 minutes
                    # vendor object not found by this id
                    else:
                        return Response(status=status.HTTP_404_NOT_FOUND)

                # -------------- setting distance+reach+increment_of_counter
                distance = round(
                    haversine_distance(
                        vendor.latitude,
                        vendor.longitude,
                        lat,
                        lon,
                    ),
                    1,
                )
                reach_time =distance_to_travel_time(distance)
                ser_data["distance"] = distance
                ser_data["reach_time"] = reach_time
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


# class FavListViewset(viewsets.ModelViewSet):
#     """THis viewset handles CRUD of Fav List"""

#     serializer_class = FavItemSerializer
#     permission_classes = [IsAuthenticated, IsHavingFavlist]

#     def get_serializer_context(self):
#         context = super().get_serializer_context()
#         context["favlist"] = self.request.user.favlist.id
#         return context

#     def get_queryset(self):
#         return FavItem.objects.filter(favlist=self.request.user.favlist)


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
            # data = cache.get(key, None)
            # if not data:
            categories = sorted(
                Category.objects.filter(foods__vendor_id=vendor_id)
                .distinct()
                .prefetch_related(
                    Prefetch(
                        "foods",
                        Food.objects.filter(vendor_id=vendor_id, is_available=True),
                    )
                ),
                key=lambda x: strxfrm(x.name),
                reverse=True,
            )
            ser = CategoryVendorFoodsSerializer(categories, many=True)
            data = ser.data
            # cache.set(key, data, 5 * 60)  # cache for 5 minutes
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
        # try:
        data = self.request.query_params
        category_id = data.get("category_id", None)
        user_location = data.get("location", None)
        city = data.get("city", None)
        if not (category_id and user_location and city):
            return Vendor.objects.none()
        city = str(city).lower()
        lat, lon = geohash.decode(user_location)
        user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
        nearest_h3s = h3.grid_disk(user_h3, 20)

        local_vendors_matching_category = (
            Vendor.objects.filter(
                city=city,
                h3_id__in=nearest_h3s,
                foods__category__id=category_id,
                is_approved=True,
            )
            .distinct()
            .prefetch_related(
                Prefetch(
                    "foods",
                    queryset=Food.objects.filter(
                        category_id=category_id
                    ).select_related("category"),
                )
            )
            .select_related("user_profile")
            .only(
                "id",
                "vendor_name",
                "avg_rating",
                "foods",
                "rating_count",
                "user_profile",
            )
        )
        # explain by postgres
        # print(local_vendors_matching_category.explain(verbose=True, DiscountedFoodSerializerManyanalyze=True),"==============")
        # adding reach time and distance to each vendor
        lat, lon = geohash.decode(user_location)
        for vendor in local_vendors_matching_category:
            distance = round(
                haversine_distance(
                    vendor.latitude,
                    vendor.longitude,
                    lat,
                    lon,
                ),
                1,
            )
            print(distance)
            vendor.distance = distance
            vendor.reach_time = round(distance_to_travel_time(distance), 0)
        return local_vendors_matching_category
        # except Exception as e:
        #     return Vendor.objects.none()
