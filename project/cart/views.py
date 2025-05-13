from marketplace.models import Food
from api.permissions import IsHavingCart
from .models import CartItem
from .serializers import CartSerializer
from rest_framework import views, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# Create your views here.


"""Cart API Views"""


class CartApiView(views.APIView):
    """this view enables adding/editing/deleting/retriving cart items"""

    permission_classes = [IsAuthenticated, IsHavingCart]

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
            id__in=item_ids,
            food__is_available=True,
            cart__user__id=self.request.user.id,
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
        cart_id = self.request.user.cart.id
        item = self.request.data["item-id"]
        item = CartItem.objects.filter(id=item, cart__id=cart_id).first()
        if item:
            item.delete()
        else:
            Response({"error": "no such item"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_200_OK)

    def post(self, *args, **kwargs):
        """overriding for adding new item to cart"""
        cart = self.request.user.cart
        data = self.request.data
        food_id = data.get("id", None)
        quantity = data.get("quantity", None)
        if not food_id or not quantity:
            return Response(
                {"error": "please provide id and quantity"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            food = Food.objects.get(pk=food_id)
            if food and food.is_available:
                exists = CartItem.objects.filter(cart=cart, food=food).exists()
                if not exists:
                    # if item is created now and added
                    cart_item = CartItem.objects.create(
                        cart=cart, food=food, quantity=quantity
                    )
                    # cart_item.save()
                    serializer = CartSerializer(cart)
                    return Response(serializer.data, status=status.HTTP_200_OK)
                return Response(
                    {"message": "already exists"}, status=status.HTTP_200_OK
                )

            else:
                return Response(
                    {"error": "food_not_available"}, status=status.HTTP_400_BAD_REQUEST
                )
        except:
            return Response(
                {"error": "unknown_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
