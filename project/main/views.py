from django.shortcuts import render
from django.contrib import messages
from django.db.models import Avg
from marketplace.models import Food
from main.models import FavItem, FavList
from vendor.models import  Vendor
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.http.response import JsonResponse
from .utils import query_execution_time

# Create your views here.



@login_required
def favlist(request):

    if hasattr(request.user, "favlist"):
        favlist = FavList.objects.get(user=request.user)
        favlist_items = FavItem.objects.filter(favlist=favlist)
        return render(request, "base/favlist.html", context=locals())
    return redirect("main:home")


@login_required
def add_to_favlist(request, food_id):
    if hasattr(request.user, "favlist"):
        state = FavItem.objects.get_or_create(
            favlist=request.user.favlist, food_id=food_id
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



