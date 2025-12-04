from locale import strxfrm
from marketplace.models import Category, Discount, Food, Rating
from accounts.models import CUSTOMER
from live.models import Notification
from .utils import (
    BestFoodsCounter,
    BestVendorsCounter,
    distance_reach_time,
    distance_to_travel_time,
    haversine_distance,
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
from .utils import (
    BoughtTogetherRecommender,
    get_user_info,
    StandardResultSetPagination,
    DEFAULT_H3_RESOLUTION,
    r,
)
from django.db.models import Avg
import geohash
import h3
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

    permission_classes = []
    serializer_class = FoodSerializerMany
    filter_backends = [
        filters.OrderingFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "min_price", "likes"]
    ordering = ["-likes"]
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
        return Food.objects.filter(is_available=True, vendor__city=city).select_related(
            "vendor"
        )

    @action(detail=True, methods=["get"], url_path="food-item-detail")
    def item_detail(self, request, pk):
        """provides fooditem detail with distance"""
        obj = (
            self.get_object()
        )  # this prompts filter_queryset, city existence is ensured so
        vendor = obj.vendor
        try:
            city, lat, lon = get_user_info(request)
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
        now = time.time()
        # general info
        user_cart_items_count = 0
        user_notf_count = 0
        try:
            city, lat, lon = get_user_info(request)

        except Exception as e:
            print("error", e)
            return Response(
                {
                    "cart_count": 0,
                    "notf_count": 0,
                    "categories": [],
                    "promotions": [],
                    "discounted_foods": [],
                    "local_vendors": [],
                    "cheapest_vendors": [],
                    "top_vendors": [],
                }
            )
        # -------------------- categories ----------------
        cat_key = "home_categories"
        categories = cache.get(cat_key)
        if not categories:
            # cach miss
            categories = Category.objects.filter(show_on_home=True)
            ser = CategorySerializer(categories, many=True)
            categories = ser.data
            cache.set(cat_key, categories, timeout=10 * 60)
        # ------------------ciy vendors-------------------
        city_vendors_ids = self.get_city_vendors(city)
        city_vendors = (
            Vendor.objects.filter(id__in=city_vendors_ids)
            .only(
                "id",
                "vendor_name",
                "avg_rating",
                "rating_count",
                "image",
                "logo",
                "vendor_type",
                "user_profile",
            )
        )
        # ----------------- city foods
        city_foods = (
            Food.objects.filter(is_available=True, vendor__city=city)
            .select_related("discount", "vendor")
            .only(
                "id",
                "name",
                "image",  #
                "discount",
                "vendor",
                "min_price",
                "category",
                "likes",
            )
        )
        # ------------------------ promotions
        promotions = Promotion.objects.filter(city=city)
        promotion_serializer = PromotionSerializer(promotions, many=True)
        # -------------------------- discounted foods
        dis_foods_key = f"city:{city}:dis_foods"
        discounted_foods_ids = cache.get(dis_foods_key, None)
        if not discounted_foods_ids:
            discounted_foods_ids = city_foods.filter(
                discount__is_active=True,
            ).values_list("id", flat=True)

            cache.set(dis_foods_key, discounted_foods_ids, 10 * 60)
        discounted_foods_final = city_foods.filter(
            id__in=discounted_foods_ids
        ).select_related("vendor")
        distance_reach_time(discounted_foods_final, lat, lon)
        discounted_foods_ser = DiscountedFoodSerializerMany(
            discounted_foods_final, many=True
        )

        # ----------------------- local vendors
        user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
        nearest_h3s = h3.grid_disk(user_h3, 10)
        # filter in db for existing nearby  open city vendors
        local_vendors = city_vendors.filter(
            h3_id__in=nearest_h3s,
        ).select_related(
            "user_profile"
        )[:10]
        distance_reach_time(local_vendors, lat, lon, "vendor")
        local_vendors_ser = VendorSerializerMany(local_vendors, many=True)

        # ------------------------- cheapest vendors
        cheapest_vendors = city_vendors.annotate(
            avg_price=Avg("foods__min_price")
        ).order_by("avg_price")[:10]
        distance_reach_time(cheapest_vendors, lat, lon, "vendor")
        cheapest_vendors_ser = VendorSerializerMany(cheapest_vendors, many=True)

        # --------------------------- top vendors
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
        city, lat, lon = get_user_info(request)
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
        ).select_related("vendor")
        try:
            """here can be an error due to long distance of user and vendor,
            since h3 library does not work for a big distance"""
            distance_reach_time(discounted_foods_final, lat, lon)
        except:
            pass
        # paginating and sending the result
        paginator = StandardResultSetPagination()
        qs = paginator.paginate_queryset(discounted_foods_final, request)
        ser = DiscountedFoodSerializerMany(qs, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["get"], url_path="local-vendors")
    def local_vendors(self, request):
        city, lat, lon = get_user_info(request)
        city_vendors_ids = self.get_city_vendors(city)
        user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
        nearest_h3s = h3.grid_disk(user_h3, 10)
        vendors = Vendor.objects.filter(
            id__in=city_vendors_ids,
            h3_id__in=nearest_h3s,
        ).select_related("user_profile")[:10]
        # adding distance property to each vendor
        distance_reach_time(vendors, lat, lon, "vendor")
        paginator = StandardResultSetPagination()
        qs = paginator.paginate_queryset(vendors, request)
        ser = VendorSerializerMany(qs, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["get"], url_path="cheapest-vendors")
    def cheapest_vendors(self, request):
        city, lat, lon = get_user_info(request)
        city_vendors_ids = self.get_city_vendors(city)
        vendors = (
            Vendor.objects.filter(id__in=city_vendors_ids)
            .annotate(avg_price=Avg("foods__min_price"))
            .order_by("avg_price")[:5]
        )
        distance_reach_time(vendors, lat, lon, "vendor")
        paginator = StandardResultSetPagination()
        qs = paginator.paginate_queryset(vendors, request)
        ser = VendorSerializerMany(qs, many=True)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["get"], url_path="top-vendors")
    def top_vendors(self, request):
        """this endpoint returns top rating and most viewed vendors in the city"""
        city, lat, lon = get_user_info(request)
        counter = BestVendorsCounter(city)
        top = counter.read_counts(10)
        top_vendors = Vendor.objects.filter(
            is_approved=True, city=city, id__in=top
        ).order_by("-avg_rating")[:5]
        distance_reach_time(top_vendors, lat, lon, "vendor")
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
        city, lat, lon = get_user_info(request)
        vendors_ids = self.get_city_vendors(city)
        print(vendors_ids,"ids")
        # foods limited to 3 IMPORTANT FOR PERFORMANCE
        foods_with_limit = (
            Food.objects.annotate(
                rn=Window(
                    expression=RowNumber(),
                    partition_by=[F("vendor_id")],
                    order_by=F("likes").desc(),
                )
            )
            .filter(rn__lte=3)  # limit to 3 foods per vendor
            .only(
                "id",
                "vendor_id",
                "name",
                "image",
                "min_price",
            )
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
        print("vendors found",vendors)
        distance_reach_time(vendors, lat, lon, "vendor")
        paginator = StandardResultSetPagination()
        qs = paginator.paginate_queryset(vendors, request)
        ser = VendorSerializerWithFoodImages(qs, many=True)
        print(ser.data)
        return paginator.get_paginated_response(ser.data)

    @action(detail=False, methods=["get"], url_path="nearby-vendors-on-map")
    def nearby_vendors_on_map(self, request):
        """
        this endpoint returns a list of serialized vendors to be shown on map
        it uses AbstractVendorSerializer.
        note: h3.grid_disk returns amount of n-times hexagons away
        as circle from current hex
        """
        city, lat, lon = get_user_info(request)
        city_vendors_ids = self.get_city_vendors(city)
        user_h3 = h3.latlng_to_cell(lat, lon, DEFAULT_H3_RESOLUTION)
        nearest_h3s = h3.grid_disk(user_h3, 20)
        # filter in db for existing nearby  open city vendors
        vendors = Vendor.objects.filter(
            id__in=city_vendors_ids,
            h3_id__in=nearest_h3s,
        ).only("vendor_name", "id", "location", "id", "vendor_type")
        ser = AbstractVendorSerializer(vendors, many=True)
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
    permission_classes = [AllowAny]
    pagination_class = StandardResultSetPagination
    serializer_class = FoodSerializerMany
    queryset = Food.objects.filter(is_available=True)
    filter_backends = [
        CustomFoodSearch,
        DjangoFilterBackend,
        CustomFoodOrdering,
    ]
    filterset_class = FoodFilterSet

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
    permission_classes = [AllowAny]

    def get_queryset(self):
        """returns rating objects of a related object [food, vendor, carrier]"""
        object_id = self.request.query_params.get("obj_id", None)
        # ------------ ownership in case of delete or update of rating
        if self.request.method in ("DELETE", "PATCH"):
            if (
                not self.request.user.is_authenticated
                or self.request.user.role != CUSTOMER
            ):
                return Rating.objects.none()
            return Rating.objects.filter(user=self.request.user)
        if not object_id:
            return Rating.objects.none()
        # -------------------------- getting object
        try:
            ct = ContentType.objects.get_for_model(Vendor)
            query_set = Rating.objects.filter(
                content_type=ct, object_id=int(object_id), enabled=True
            ).order_by("-rating")
            return query_set
        except:
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
        """overriden to handle custom rating creation and food likes"""
        if self.request.user.is_anonymous:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
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
        #---------------  handling likes of foods
        if liked_foods:
            for f in liked_foods:
                try:
                    food = Food.objects.get(id=f)
                    food.likes += 1
                    food.save()
                except Food.DoesNotExist:
                    pass
                except Exception as e:
                    print("error in like food:",e)
        # -------------  handling rating update if updated
        if previous:
            # prviously exists, performing update
            ser = self.get_serializer(previous, data=rating_data)
            ser.is_valid(raise_exception=True)
            ser.save()
            ser.instance.related_obj.update_avg_rating()
            return Response(status=status.HTTP_200_OK)
        # --------------- new rating
        else:
            serializer = self.get_serializer(data=rating_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(
                serializer
            )
            instance = serializer.instance
            vendor = None
            ct = ContentType.objects.get_for_model(Vendor)
            instance.content_type = ct
            vendor = Vendor.objects.filter(id=obj_id).first()
            if not vendor:
                return Response(
                    {"detail": "no_such_vendor"}, status=status.HTTP_400_BAD_REQUEST
                )

            instance.object_id = int(obj_id)
            instance.save()
            vendor.update_avg_rating()
            return Response(serializer.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        """setting user manually from request context"""
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        """updating obj rating avg and count if one of its ratings is deleted"""
        if self.request.user.is_anonymous:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        rating = self.get_object()
        obj = rating.related_obj
        rating.delete()
        obj.update_avg_rating()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoriesReadAPIView(views.APIView):
    """This endpoint a list of categories for vendors when adding new fooditems"""
    http_method_names = ["get"]
    def get(self, *args, **kwargs):
        cats = Category.objects.all()
        ser = CategorySerializer(cats,many=True)
        return Response(ser.data)


class PublicVendorDetail(views.APIView):
    """this view enables a normal user see a vendor detail with its fooditems avaialble"""

    serializer_class = PublicVendorSerializer
    permission_classes = [AllowAny]
    queryset = Vendor.objects.filter(is_approved=True)

    def vendor_detail_key(self, id):
        return f"vdr:{id}:dt"

    def get(self, *args, **kwargs):
        """
        This initially tries to get vendor details from cache, if not found,
        then queries db and serialize and cache.
        we have to use caching since its not only about vendor but its menue.
        """
        request = self.request
        request_data = request.query_params
        city, lat, lon = get_user_info(request)
        vendor_id = request_data.get("id", None)
        if vendor_id:
            try:
                # ------------------------ getting vendor details either cache or db
                ser_data = None
                vendor_in_cache = cache.get(self.vendor_detail_key(vendor_id))
                vendor = Vendor.objects.get(is_approved=True, id=vendor_id, city=city)
                # ---------------- cache
                if vendor_in_cache:
                    ser_data = vendor_in_cache.copy()
                else:
                    if vendor:
                        vendor_foods = Food.objects.filter(
                            vendor_id=vendor.id, is_available=True
                        )
                        featured_items = vendor_foods.filter(is_featured=True)
                        vendor_categories = sorted(
                            list(
                                set(vendor_foods.values_list("category__name", flat=True))
                            ),
                            key=lambda x: strxfrm(x) if x else "",
                            reverse=True,
                        )

                        discounted_foods = vendor_foods.filter(
                            discount__is_active=True
                        ).only("id", "name", "image", "min_price", "category")
                        vendor.featured_items = featured_items  # later on we decide
                        vendor.discounted_foods = discounted_foods
                        vendor.categories = vendor_categories
                        vendor.categories_count = len(vendor_categories)
                        ser = PublicVendorSerializer(vendor)
                        ser_data = ser.data
                        cache.set(
                            self.vendor_detail_key(vendor_id), ser_data, 5 * 60
                        )  # cache for 5 minutes
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
                reach_time = distance_to_travel_time(distance)
                ser_data["distance"] = distance
                ser_data["reach_time"] = int(reach_time)
                counter = BestVendorsCounter(str(city))
                counter.update_counts(vendor_id)
                return Response(ser_data, status=status.HTTP_200_OK)
            except Vendor.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                print("error occured in vendor detail", e, e.args)
                return Response(status=status.HTTP_501_NOT_IMPLEMENTED)
        else:
            return Response(
                {"detail": "no_id_provided"}, status=status.HTTP_400_BAD_REQUEST
            )


class ListVendorFoods(views.APIView):
    """
    THis returns foods of a vendor either sorted by min price
    or grouped by category
    this endpoint works as the second part of vendor detail 
    """
    permission_classes = [AllowAny]
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
            return Response(data)
        except Exception as e:
            print("error occured in vendor foods list", e)
            return Response(status=status.HTTP_501_NOT_IMPLEMENTED)

    def get_cache_key(self, vendor_id):
        return f"vendor:{vendor_id}:foods"


class FoodsByCategory(generics.ListAPIView):
    """THis returns foods by category, also pagintaes the result"""

    serializer_class = CategoryVendorSerializer
    pagination_class = StandardResultSetPagination
    permission_classes = [AllowAny]

    def get_queryset(self):
        """filtering by category"""
        try:
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
                vendor.distance = distance
                vendor.reach_time = round(distance_to_travel_time(distance), 0)
            return local_vendors_matching_category
        except Exception as e:
            print("error in foods by category",e)
            return Vendor.objects.none()
