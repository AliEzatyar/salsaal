from django.shortcuts import render
from django.contrib import messages
from django.db.models import Avg
from marketplace.models import Product
from main.models import FavItem, FavList
from vendor.models import Rating, Vendor
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.http.response import JsonResponse
from .utils import query_execution_time

# Create your views here.


def home(request, cat=None):
    # listing top 5 vendors
    products = Product.objects.filter(is_available=True).select_related("vendor")
    if cat:
        temp = products.filter(category__name=cat).exists()
        if temp:
            products = products.filter(category__name=cat)

    week_sold_products = products
    top_selling_products = products
    trending_products = products
    recently_viewed = products
    vendors = Vendor.objects.annotate(
        average_rating=(
            Avg("ratings__c_service")
            + Avg("ratings__p_quality")
            + Avg("ratings__d_time")
        )
    ).filter(ratings__isnull=False)[:5]
    return render(request, "base/home.html", context=locals())


@login_required
def favlist(request):

    if hasattr(request.user, "favlist"):
        favlist = FavList.objects.get(user=request.user)
        favlist_items = FavItem.objects.filter(favlist=favlist)
        return render(request, "base/favlist.html", context=locals())
    return redirect("main:home")


@login_required
def add_to_favlist(request, product_id):
    if hasattr(request.user, "favlist"):
        state = FavItem.objects.get_or_create(
            favlist=request.user.favlist, product_id=product_id
        )
        if state[1]:
            # if item is created now
            return JsonResponse({"OK": 1})
        return JsonResponse({"OK": 0})


@login_required
def delete_from_favlist(request, item_id):
    if hasattr(request.user, "favlist"):
        favitem = FavItem.objects.filter(id=item_id).first()
        if favitem:
            favitem.delete()
            return JsonResponse({"OK": 1})
        return JsonResponse({"OK": 0})



