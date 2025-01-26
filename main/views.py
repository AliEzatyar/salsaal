from django.shortcuts import render
from django.contrib import messages
from django.db.models import Avg
from vendor.models import Rating, Vendor

# Create your views here.


def home(request):
    # listing top 5 vendors
    vendors = Vendor.objects.annotate(
        average_rating=(
            Avg("ratings__c_service")
            + Avg("ratings__p_quality")
            + Avg("ratings__d_time")
        )
    ).filter(ratings__isnull=False)[:5]
    return render(request, "base/home.html", context=locals())
