import json
from django.shortcuts import render
from django.http.response import HttpResponse, JsonResponse
from marketplace.models import Product
from .models import Cart, CartItem
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect


# Create your views here.


@login_required
def show_cart(request):
    cart = Cart.objects.get_or_create(user=request.user)[0]
    items = CartItem.objects.filter(cart=cart).select_related("product__vendor")
    return render(request, "cart/cart.html", context=locals())


@login_required
def add_to_cart(request, product_id):
    product = Product.objects.filter(pk=product_id).first()
    if product:
        cart = Cart.objects.get_or_create(user=request.user)[0]
        state = CartItem.objects.get_or_create(cart=cart, product=product)
        if state[1]:
            # if item is created now
            cart_item = state[0]
            cart_item.save()
            cart.items.add(cart_item)
            return JsonResponse({"OK": 1})
        # not added
        return JsonResponse({"OK": 0})


@login_required
def delete_cart_item(request, item_id):
    cart = request.user.cart
    item = CartItem.objects.filter(id=item_id).first()
    if item and item in cart.items.all():
        item.delete()
        return JsonResponse({"OK": 1})
    return redirect({"OK": 0})


@require_POST
@login_required
def edit_cart(request):
    cart = request.user.cart
    body = json.loads(request.body)
    items = body["items"]
    for item_id, quantity in items:
        item = CartItem.objects.filter(id=item_id).first()
        if item:
            item.quantity = quantity
            item.save()

    return HttpResponse("تغییرات موفقانه ذخیره شد")
