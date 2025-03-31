"""this file contains search, sort and filter logic"""

import django_filters

from marketplace.models import Product

class ProductFilterSet(django_filters.FilterSet):
    """this class customizes filtering of products"""
    is_expensive= django_filters.BooleanFilter(method="filter_expensive")
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr="lte")
    category = django_filters.CharFilter(
        field_name="category__name", lookup_expr="iexact"
    )
    min_rating = django_filters.NumberFilter(field_name="rating",lookup_expr="gte")

    class Meta:
        model = Product
        fields = ["min_price", "max_price", "category","min_rating"]

    def filter_expensive(self,queryset, name,value):
        """making more advanced filtering logic here"""
        if value: # if expensive=True -> return expensive ones only
            return queryset.filter(price__gte=8000)
        
        # expensive=False -> return cheap products
        return queryset.filter(price__lte=1000)