"""this file contains search, sort and filter logic"""

import time
import geohash
import django_filters
import h3
from order.models import ORDER_STATUS_CHOICES, Order
from marketplace.models import Food
from django.utils.timezone import now, timedelta, datetime
from rest_framework.filters import SearchFilter
from rest_framework.filters import OrderingFilter
from django.db.models import F
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point
from rest_framework.filters import OrderingFilter
from marketplace.utils import (
    distance_to_travel_time,
    haversine_distance,
)
from multiVend.country.info import DEFAULT_SEARCH_DISTANCE
from vendor.models import Vendor
from django.contrib.postgres.search import TrigramSimilarity
from django.utils.timezone import now


class FoodFilterSet(django_filters.FilterSet):
    """this class customizes filtering of foods"""

    # is_expensive = django_filters.BooleanFilter(method="filter_expensive")
    min_price = django_filters.NumberFilter(field_name="min_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="min_price", lookup_expr="lte")
    discounted = django_filters.BooleanFilter(method="filter_by_discounted")

    class Meta:
        model = Food
        fields = ["min_price", "max_price", "discounted"]

    def filter_by_discounted(self, queryset, name, value):
        return queryset.filter(discount__amount__gt=0)


class CustomFoodOrdering(OrderingFilter):
    ordering_fields = ["min_price", "likes"]  # can include real fields
    ordering = ["min_price"]  # default
    ordering_param = "sort_by"

    def filter_queryset(self, request, queryset, view):
        """overriden for adding reach time for every food,
        since this filter is applied last, pythonic attrs are kept"""
        queryset = super().filter_queryset(request, queryset, view)

        request_data = request.query_params
        sort_by = request_data.get("sort_by", None)
        user_location = request_data.get("location", None)
        # Now add temporary attribute
        if user_location:
            lat, lon = geohash.decode(user_location)
            for food in queryset:
                distance = round(
                    haversine_distance(
                        food.vendor.latitude,
                        food.vendor.longitude,
                        lat,
                        lon,
                    ),
                    1,
                )
                food.reach_time = round(distance_to_travel_time(distance))
        if sort_by:
            if sort_by == "-reach_time":
                return sorted(queryset, key=lambda x: x.reach_time, reverse=True)
            elif sort_by == "reach_time":
                return sorted(queryset, key=lambda x: x.reach_time)

        return queryset


class CustomFoodSearch(SearchFilter):
    search_param = "query"

    def filter_queryset(self, request, queryset, view):
        """overriden for custom search"""
        request_data = request.query_params
        city = request_data.get("city", None)
        if not city:
            return Food.objects.none()
        city = str(city).lower()
        search_param = request_data.get(self.search_param)
        # if search param value is void and no discount is searchd
        if not search_param or not search_param.strip():
            return queryset.none()
        """
            Here is subtle case to consider, 
            django orm does not allow filter after a qs is limited or [:n]
            so when discounted flag is true in request header, we don't limit it.
        """
        if request_data.get("discounted"):
            foods = (
                Food.objects.filter(vendor__city=city)
                .annotate(similarity=TrigramSimilarity("name", search_param))
                .filter(similarity__gte=0.2)
                .select_related("vendor")
            )
        else:
            foods = (
                Food.objects.filter(vendor__city=city)
                .annotate(similarity=TrigramSimilarity("name", search_param))
                .filter(similarity__gte=0.2)
                .select_related("vendor")
                .order_by("-similarity")[:20]
            )
        return foods


class VOrderFilterSet(django_filters.FilterSet):
    """this class customizes filtering of orders to vendors"""

    status = django_filters.CharFilter(method="filter_by_status")
    created_at = django_filters.DateFilter(method="filter_by_date")
    start = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    end = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Order
        fields = ["status", "start", "end", "created_at"]

    def filter_queryset(self, queryset):
        return super().filter_queryset(queryset)

    def filter_by_status(self, queryset, name, value):
        """returns orders by status"""
        # if incorrect filtering option is requested -> []
        if not value in ([val[0] for val in ORDER_STATUS_CHOICES]):
            return Order.objects.none()

        if value == "cancelled":
            return queryset.filter(status=ORDER_STATUS_CHOICES[0][0])

        elif value == "waiting":
            today = now()
            return queryset.filter(
                created_at__date=today.date(), status=ORDER_STATUS_CHOICES[1][0]
            )
        elif value == "preparing":
            today = now()
            return queryset.filter(
                created_at__date=today.date(), status=ORDER_STATUS_CHOICES[2][0]
            )

        elif value == "carrying":
            today = now()
            return queryset.filter(
                created_at__date=today.date(), status=ORDER_STATUS_CHOICES[3][0]
            )
        elif value == "delivered":
            return queryset.filter(status=ORDER_STATUS_CHOICES[4][0])
        else:
            return Order.objects.none()

    def filter_by_date(self, queryset, name, value):
        """return orders on a specifc date"""
        try:
            return queryset.filter(created_at__date=value)
        except:
            return Order.objects.none()


class CustomVendorOrdering(OrderingFilter):
    """
    this ordering class sorts vendors by distance
    used in marketplace/VendorSearchViewset
    """

    ordering_fields = ["avg_rating", "rating_count", "reach_time", "distance"]
    ordering = ["-avg_rating"]  # default
    ordering_param = "sort_by"

    def filter_queryset(self, request, queryset, view):
        """overriden to handle distance sorting"""
        ordering = self.get_ordering(request, queryset, view)

        if ordering:
            if ordering == "distance":
                return sorted(queryset, key=lambda x: x.distance)
            elif ordering == "-distance":
                return sorted(queryset, key=lambda x: x.distance, reverse=True)
            return queryset.order_by(*ordering)
        return queryset


class CustomVendorSearch(SearchFilter):
    """
    this search filter class is used in marketplace/VendorSearchViewset
    """
    search_param = "query"

    def filter_queryset(self, request, queryset, view):
        # if search param value is void
        # getting user location
        request_data = request.query_params
        search_param = request_data.get(self.search_param)
        location = request_data.get("location", None)
        city = request_data.get("city", None)
        max_distance = request_data.get("max_distance", None)
        if not (location and city):
            return queryset.none()
        city = str(city).lower()
        # determinig user location
        try:
            # decode location data
            if max_distance:
                max_distance = float(max_distance)
            lat, lon = geohash.decode(location)
            location = Point(float(lon), float(lat), srid=4326)
        except Exception as e:
            return queryset.none()
        # searching for vendors nearby at max distance
        if search_param:
            vendors = (
                Vendor.objects.filter(city=city)
                .annotate(similarity=TrigramSimilarity("vendor_name", search_param))
                .filter(similarity__gt=0.2)
                .annotate(distance=Distance("location", location))
                .filter(
                    distance__lte=(
                        D(km=max_distance)
                        if max_distance
                        else D(km=DEFAULT_SEARCH_DISTANCE)
                    )
                )
                .annotate(reach_time=F("distance") / 7 / 60)
                .order_by("-similarity")
            )
            return vendors
        # return vendors in city
        vendors = (
            Vendor.objects.filter(city=city)
            .annotate(distance=Distance("location", location))
            .filter(
                distance__lte=(
                    D(km=max_distance)
                    if max_distance
                    else D(km=DEFAULT_SEARCH_DISTANCE)
                )
            )
            .annotate(reach_time=F("distance") / 7 / 60)
            .order_by("distance")
        )
        print(vendors)
        return vendors


class VendorFilterSet(django_filters.FilterSet):
    avg_rating = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="gte")
    distance = django_filters.NumberFilter()

    class Meta:
        model = Vendor
        fields = ["avg_rating", "vendor_type"]
