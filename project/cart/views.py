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
    if product and product.existing_amount > 0:
        cart = Cart.objects.get_or_create(user=request.user)[0]
        state = CartItem.objects.get_or_create(cart=cart, product=product)
        if state[1]:
            # if item is created now and added
            product.existing_amount -= 1
            cart_item = state[0]
            cart_item.save()
            cart.items.add(cart_item)
            return JsonResponse({"saved": True})
        else:
            # if item was added before
            return JsonResponse({"saved":False,"error": "exists_before"})
    else:
        return JsonResponse({"saved": False, "error": "no_existing"})


@login_required
def delete_cart_item(request, item_id):
    cart = request.user.cart
    item = CartItem.objects.filter(id=item_id).first()
    if item and item in cart.items.all():
        item.delete()
        return JsonResponse(
            {"saved": True, "products_total_price": cart.calculate_total()}
        )
    return redirect({"saved": False})


@require_POST
@login_required
def edit_cart(request):
    body = json.loads(request.body)
    items = body["items"]
    for item_id, quantity in items:
        item = CartItem.objects.filter(id=item_id).first()
        if item and item.product.existing_amount > int(quantity):
            item.quantity = quantity
            item.save()
        else:
            continue
    cart = request.user.cart
    return JsonResponse({"saved": True, "products_total_price": cart.calculate_total()})

