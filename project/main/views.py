from django.shortcuts import render
from django.contrib import messages
from django.db.models import Avg
from catalog.models import Product
from vendor.models import Rating, Vendor

# Create your views here.


def home(request, cat=None):
    # listing top 5 vendors
    products = Product.objects.filter(is_available=True)
    if cat:
        temp = products.filter(category__name=cat).exists()
        if temp:
            products = products.filter(category__name=cat)
            
    week_sold_products = products
    top_selling_products = products
    vendors = Vendor.objects.annotate(
        average_rating=(
            Avg("ratings__c_service")
            + Avg("ratings__p_quality")
            + Avg("ratings__d_time")
        )
    ).filter(ratings__isnull=False)[:5]
    return render(request, "base/home.html", context=locals())
