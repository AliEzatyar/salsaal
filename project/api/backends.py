"""this file contains search, sort and filter logic"""
from django_jalali.db.models import jdatetime
import django_filters
from order.models import ORDER_STATUS_CHOICES, Order
from marketplace.models import Food
from django.utils.timezone import now, timedelta


class FoodFilterSet(django_filters.FilterSet):
    """this class customizes filtering of foods"""
    is_expensive= django_filters.BooleanFilter(method="filter_expensive")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = django_filters.CharFilter(
        field_name="category__name", lookup_expr="iexact"
    )
    min_rating = django_filters.NumberFilter(field_name="rating",lookup_expr="gte")

    class Meta:
        model = Food
        fields = ["min_price", "max_price", "category","min_rating"]

    def filter_expensive(self,queryset, name,value):
        """making more advanced filtering logic here"""
        if value: # if expensive=True -> return expensive ones only
            return queryset.filter(price__gte=8000)

        # expensive=False -> return cheap foods
        return queryset.filter(price__lte=1000)


class VOrderFilterSet(django_filters.FilterSet):
    """this class customizes filtering of orders to vendors"""
    status = django_filters.CharFilter(method="filter_by_status")
    date_range = django_filters.CharFilter(method="filter_by_date_range")
    created_at = django_filters.DateFilter(method="filter_by_date")

    class Meta:
        model = Order
        fields = ["status", "date_range","created_at"]

    def filter_by_status(self, queryset, name, value):
        """making more advanced filtering logic here"""
        if not value in ([val[0] for val in ORDER_STATUS_CHOICES]):
            return queryset

        if value == "cancelled":  
            return queryset.filter(status=ORDER_STATUS_CHOICES[0][0])

        if value == "waiting": 
            return queryset.filter(status=ORDER_STATUS_CHOICES[1][0])

        if value == "processing": 
            return queryset.filter(status=ORDER_STATUS_CHOICES[2][0])

        if value == "carrying": 
            return queryset.filter(status=ORDER_STATUS_CHOICES[3][0])

        if value == "submitted": 
            return queryset.filter(status=ORDER_STATUS_CHOICES[4][0])

    def filter_by_date_range(self, queryset, name, value):
        today = now().date()
        
        if not value in ("today","last_week","yesterday"):
            return queryset

        if value == "today":
            return queryset.filter(created_at=today)
        if value == "yesterday":
            return queryset.filter(created_at__date=today -timedelta(days=1))
        if value == "last_week":
            return queryset.filter(created_at__gte=today - timedelta(days=7))

    def filter_by_date(self,queryset,name,value):
        return queryset.filter(created_at__date=value)