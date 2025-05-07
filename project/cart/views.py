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

