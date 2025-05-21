from marketplace.models import Category, FavItem, FavList, Food, Rating
from order.models import Order, OrderItem
from accounts.models import CUSTOMER
from .utils import haversine_distance as distance_calculator
from api.backends import FoodFilterSet
from vendor.models import Vendor
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

from django.db.models.aggregates import Count, Avg, Sum
from django.contrib.contenttypes.models import ContentType
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
from django.utils import timezone
from rest_framework import filters, permissions, status, views, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.mixins import RetrieveModelMixin
from rest_framework.permissions import AllowAny
from api.permissions import IsHavingFavlist, NotAdmin

"""Marketplace API Views"""


# home page view
class MarketplaceViewset(viewsets.ReadOnlyModelViewSet):
    """
    This view  handles representation of foods to normal users.
    For food detail, this view requires user location saved on profile instance. if user is not
    auhtenticated, query params 'lat' and 'lon' must be sent.
    """

    queryset = Food.objects.filter(is_available=True)
    serializer_class = FoodSerializerMany
    permission_classes = [NotAdmin]

    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "min_price", "avg_rating"]
    ordering = ["-avg_rating"]
    # filering
    filterset_class = FoodFilterSet
    # searching
    search_fields = ["name", "category__name", "description", "vendor__vendor_name"]

    def get_object(self):
        obj = super().get_object()
        if not obj.vendor.is_approved:
            return None
        return obj

    @action(detail=True, methods=["get"], url_path="food-item-detail")
    def item_detail(self, request, pk):
        """provides fooditem detail with distance"""
        obj = self.get_object()
        data = request.query_params
        lat = data.get("lat", None)
        lon = data.get("lon", None)
        vendor_profile = obj.vendor.user_profile

        if not (lat and lon):
            # if authenticated, get location data from profile
            if self.request.user.is_authenticated:
                user_profile = self.request.user.profile
                if user_profile.lattitude and user_profile.longitude:
                    distance = distance_calculator(
                        float(vendor_profile.lattitude),
                        float(vendor_profile.longitude),
                        float(user_profile.lattitude),
                        float(user_profile.longitude),
                    )
                    serializer = CFoodSerializerDetail(instance=obj)
                    return Response({"item": serializer.data, "distance": distance})
                # re-send the request either with lat,lon or updated profile prompt
                return Response(
                    {"detail": "user_has_not_set_location"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {"detail": "no_location_provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        # client app have provided lat and lon
        else:
            try:
                distance = distance_calculator(
                    float(vendor_profile.lattitude),
                    float(vendor_profile.longitude),
                    float(lat),
                    float(lon),
                )
                serializer = CFoodSerializerDetail(instance=obj)
                return Response({"item": serializer.data, "distance": distance})
            except Exception as e :
                return Response(status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"],url_path="all-categories")
    def categories(self, request):
        """this endpoint returns available categories"""
        categories = Category.objects.filter(show_on_home=True).values("name", "id")
        ser = CategorySerializer(categories, many=True)
        return Response(ser.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"],url_path="nearby-resturants")
    def nearby_resturants(self, request):
        """this endpoint returns nearby_vendors"""
        region = request.data.get("region", None)
        lat = request.data.get("lat", None)
        lon = request.data.get("lon", None)
        max_distance = request.data.get("max_distance", 10)  # km
        try:
            max_distance = float(max_distance)
        except:
            max_distance = 10

        if request.user.is_authenticated:
            region = request.user.region
            user_location = request.user.profile.location
        else:
            if not region:
                return Response({"detail": "Please send region as 'XY'."}, status=400)
            if not lat or not lon:
                return Response(
                    {"detail": "Latitude and longitude are required."}, status=400
                )
            try:
                user_location = Point(float(lon), float(lat), srid=4326)
            except (TypeError, ValueError):
                return Response({"detail": "Invalid coordinates."}, status=400)
            user_location = Point(float(lon), float(lat), srid=4326)

        vendors = (
            Vendor.objects.filter(is_approved=True, user__region=region)
            .annotate(distance=Distance("user_profile__location", user_location))
            .filter(distance__lte=D(km=max_distance))
            .order_by("distance")[:5]
        )
        ser = VendorSerializerMany(vendors, many=True, context={"request": request})
        return Response(ser.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"],url_path="week-trending")
    def week_trending(self, request):
        region = request.data.get("region", None)
        if request.user.is_authenticated:
            region = request.user.region
        if not region:
            return Response({"detail": "Please send region as 'XY'."}, status=400)

        week_ago = timezone.now() - timezone.timedelta(weeks=1)
        orders = Order.objects.filter(
            user__region=region, created_at__gte=week_ago
        ).values("id")

        top_week_foods = (
            OrderItem.objects.filter(order_id__in=orders)
            .values("food")
            .annotate(item_count=Count("id"))
            .order_by("-item_count")[:5]
        )
        foods_ids = [item["food"] for item in top_week_foods]
        foods = Food.objects.filter(id__in=foods_ids)
        ser = FoodSerializerMany(foods, many=True)
        return Response(ser.data)


# search
class SearchApiView(views.APIView):
    """This api view handles searching for both food and vendor objects considering distance"""

    permission_classes = [permissions.AllowAny]

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
            return Response({"error":"no_user_location"},status=status.HTTP_400_BAD_REQUEST)

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
            Vendor.objects.filter(
                vendor_name__icontains=query, is_approved=True
            )
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


class RatingViewSet(viewsets.ModelViewSet):
    permission_classes = [NotAdmin]
    http_method_names = ["get", "post", "delete","patch"]
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
        rating_type = self.request.query_params.get("type",None)
        rating_limit = self.request.query_params.get("rating_limit",None)
        # user should be logged in and own the rating object
        if self.request.method in ("DELETE","PATCH") :
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
            if rating_limit  and rating_limit > 0:
                query_set = Rating.objects.filter(content_type=ct,object_id=int(object_id),enabled=True).order_by("-rating")[:rating_limit]
            else:
                query_set = Rating.objects.filter(
                    content_type=ct, object_id=int(object_id), enabled=True
                ).order_by('-rating')
            return query_set
        except:
            # if any problem, no rating is returned
            return Rating.objects.none()

    def create(self, request, *args, **kwargs):
        """overriden, obj_id, type,"""
        if not self.request.user.is_authenticated or self.request.user.role !=CUSTOMER:
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


# categories
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


# vendor detail for public users
class PublicVendorDetail(RetrieveModelMixin, viewsets.GenericViewSet):
    """this view enables a normal user see a vendor detail with its menue"""

    serializer_class = PublicVendorSerializer
    permission_classes = [AllowAny]
    queryset = Vendor.objects.filter(is_approved=True)


class FavListViewset(viewsets.ModelViewSet):
    serializer_class = FavItemSerializer
    permission_classes = [permissions.IsAuthenticated,IsHavingFavlist]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['favlist'] = self.request.user.favlist.id
        return context
    
    def get_queryset(self):
        return FavItem.objects.filter(favlist=self.request.user.favlist)