import json
from django.shortcuts import render
from django.http.response import JsonResponse
from marketplace.models import Food
from .models import Cart, CartItem
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.shortcuts import redirect
from .serializers import CartSerializer
from rest_framework import views
from rest_framework import status
from rest_framework.response import Response


# Create your views here.


"""Cart API Views"""


class CartApiView(views.APIView):

    def get(self, *args, **kwargs):
        """showing cart detail with items"""
        cart = self.request.user.cart
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, *args, **kwargs):
        """partial update for cart-items amount change"""
        data = self.request.data
        items_data = data["items"]
        item_ids = [item[0] for item in items_data]  # ids
        available_items = CartItem.objects.filter(
            id__in=item_ids, food__is_available=True
        )
        items_dict = {item.id: item for item in available_items}
        updated_items = []

        for item_id, quantity in items_data:
            item = items_dict.get(item_id, None)
            if item:
                item.quantity = quantity
                updated_items.append(item)

        if updated_items:
            CartItem.objects.bulk_update(updated_items, ["quantity"])
        
        # successful items quantity update
        cart = self.request.user.cart
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, *args, **kwargs):
        """deleting a cart item"""
        item = self.request.data["item-id"]
        item = CartItem.objects.filter(id=item).first()
        item.delete()
        return Response(status=status.HTTP_200_OK)

    def post(self, *args, **kwargs):
        """overriding for adding new item to cart"""
        cart = self.request.user.cart
        food_id = self.request.data["food-id"]
        food = Food.objects.filter(pk=food_id).first()
        if food and food.is_available:
            state = CartItem.objects.get_or_create(cart=cart, food=food)
            if state[1]:
                # if item is created now and added
                cart_item = state[0]
                # cart_item.save()
                cart.items.add(cart_item)
                return Response(status=status.HTTP_200_OK)
            return Response({"message": "already exists"}, status=status.HTTP_200_OK)

        else:
            return Response(
                {"error": "not_existing"}, status=status.HTTP_400_BAD_REQUEST
            )


@login_required
def show_cart(request):
    cart = Cart.objects.get_or_create(user=request.user)[0]
    items = CartItem.objects.filter(cart=cart).select_related("food__vendor")
    return render(request, "cart/cart.html", context=locals())


@login_required
def add_to_cart(request, food_id):
    food = Food.objects.filter(pk=food_id).first()
    if food and food.is_available:
        cart = Cart.objects.get_or_create(user=request.user)[0]
        state = CartItem.objects.get_or_create(cart=cart, food=food)
        if state[1]:
            # if item is created now and added
            cart_item = state[0]
            cart_item.save()
            cart.items.add(cart_item)
            return JsonResponse({"saved": True})
        else:
            # if item was added before
            return JsonResponse({"saved": False, "error": "exists_before"})
    else:
        return JsonResponse({"saved": False, "error": "no_existing"})


@login_required
def delete_cart_item(request, item_id):
    cart = request.user.cart
    item = CartItem.objects.filter(id=item_id).first()
    if item and item in cart.items.all():
        item.delete()
        return JsonResponse(
            {"saved": True, "foods_total_price": cart.calculate_total()}
        )
    return redirect({"saved": False})


@require_POST
@login_required
def edit_cart(request):
    body = json.loads(request.body)
    items = body["items"]
    for item_id, quantity in items:
        item = CartItem.objects.filter(id=item_id).first()
        if item and item.food.is_available:
            item.quantity = quantity
            item.save()
        else:
            continue
    cart = request.user.cart
    return JsonResponse({"saved": True, "foods_total_price": cart.calculate_total()})
