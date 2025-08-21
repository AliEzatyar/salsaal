"""this file contains search, sort and filter logic"""

import django_filters
from order.models import ORDER_STATUS_CHOICES, Order
from marketplace.models import Food
from django.utils.timezone import now, timedelta, datetime
from rest_framework.filters import SearchFilter
from django.db.models import Q, F
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D
import geohash
from multiVend.settings.base import DEFAULT_SEARCH_DISTANCE
from vendor.models import Vendor
from django.conf import settings


class FoodFilterSet(django_filters.FilterSet):
    """this class customizes filtering of foods"""

    # is_expensive = django_filters.BooleanFilter(method="filter_expensive")
    min_price = django_filters.NumberFilter(field_name="min_price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="min_price", lookup_expr="lte")
    avg_rating = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="gte")

    class Meta:
        model = Food
        fields = ["min_price", "max_price", "avg_rating"]


class VendorFilterSet(django_filters.FilterSet):
    avg_rating = django_filters.NumberFilter(field_name="avg_rating", lookup_expr="gte")

    class Meta:
        model = Vendor
        fields = ["avg_rating"]


class VOrderFilterSet(django_filters.FilterSet):
    """this class customizes filtering of orders to vendors"""

    status = django_filters.CharFilter(method="filter_by_status")
    date_range = django_filters.CharFilter(method="filter_by_date_range")
    created_at = django_filters.DateFilter(method="filter_by_date")

    class Meta:
        model = Order
        fields = ["status", "date_range", "created_at"]

    def filter_by_status(self, queryset, name, value):
        """filters by status"""

        # if incorrect filtering option is requested -> []
        if not value in ([val[0] for val in ORDER_STATUS_CHOICES]):
            return Order.objects.none()

        if value == "cancelled":
            return queryset.filter(status=ORDER_STATUS_CHOICES[0][0])

        if value == "waiting":
            return queryset.filter(status=ORDER_STATUS_CHOICES[1][0])

        if value == "preparing":
            return queryset.filter(status=ORDER_STATUS_CHOICES[2][0])

        if value == "carrying":
            return queryset.filter(status=ORDER_STATUS_CHOICES[3][0])

        if value == "delivered":
            return queryset.filter(status=ORDER_STATUS_CHOICES[4][0])

    def filter_by_date_range(self, queryset, name, value):

        today = now().date()
        try:
            if value == "today":
                return queryset.filter(created_at__date=today)
            elif value == "yesterday":
                return queryset.filter(created_at__date=today - timedelta(days=1))
            elif value == "last_week":
                return queryset.filter(created_at__date__gte=today - timedelta(days=7))
            elif "to" in value:
                # range
                start, end = str(value).split("to")
                start, end = datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(
                    end, "%Y-%m-%d"
                )
                return queryset.filter(created_at__date__range=(start, end))
            else:
                # if incorrect filtering option is requested -> []
                return Order.objects.none()
        except:
            return Order.objects.none()

    def filter_by_date(self, queryset, name, value):
        try:
            return queryset.filter(created_at__date=value)
        except:
            return Order.objects.none()


class CustomFoodSearch(SearchFilter):
    search_param = "q"

    def filter_queryset(self, request, queryset, view):
        """overriden for custom search"""
        search_param = request.query_params.get(self.search_param)
        # if search param value is void
        if not search_param or not search_param.strip():
            return queryset.none()

        # searching for foods
        foods = Food.objects.filter(
            Q(name__icontains=search_param) | Q(description__icontains=search_param),
        ).select_related("vendor__user_profile")
        return foods


class CustomVendorSearch(SearchFilter):
    search_param = "q"

    def filter_queryset(self, request, queryset, view):
        # if search param value is void
        # getting user location
        request_data = request.query_params
        search_param = request_data.get(self.search_param)
        location = request_data.get("location",None)
        max_distance = request_data.get("max_distance", DEFAULT_SEARCH_DISTANCE)
        user_location = None
        # determinig user location
        try:
            if location:
                # decode location data
                lat,lon = geohash.decode(location)
                user_location = Point(float(lon), float(lat), srid=4326)
        except:
            return queryset.none()

        # if no location provided, no city, incorrect city, then nothing found
        if not user_location:
            return queryset.none()
        # if no search query, return nearby vendors at max distance 
        if not search_param or not search_param.strip():
            vendors = queryset.annotate(
                distance=Distance("user_profile__location", user_location)
            ).filter(distance__lte=D(km=max_distance))
            return vendors

        # searching for vendors nearby at max distance
        vendors = (
            Vendor.objects.filter(vendor_name__icontains=search_param)
            .annotate(distance=Distance("user_profile__location", user_location))
            .filter(distance__lte=D(km=max_distance))
        )

        return vendors


