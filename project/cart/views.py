from marketplace.models import Food
from api.permissions import IsHavingCart
from marketplace.serializers import FoodSerializerMany
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
        #  suggested foods
        # recommender = BoughtTogetherRecommender()
        # suggestion_ids = recommender.suggest_foods_for(food_ids)
        # suggestion_foods = Food.objects.filter(id__in=suggestion_ids)
        # ser_many = FoodSerializerMany(suggestion_foods, many=True)
        # drinks
        if not cart.is_empty():
            vendor = cart.get_vendor()
            drinks = Food.objects.filter(is_drink=True, vendor=vendor)
            drinks_serializer = FoodSerializerMany(drinks, many=True)
            return Response(
                {
                    "cart": serializer.data,
                    "vendor_id": vendor.id,
                    "vendor_name": vendor.vendor_name,
                    "drinks": drinks_serializer.data,
                    # "suggestions": ser_many.data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "cart": serializer.data,
                "vendor_id": None,
                "vendor_name": None,
                "drinks": [],
                # "suggestions": ser_many.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, *args, **kwargs):
        """partial update for cart-items amount change and price selection"""
        cart = self.request.user.cart
        data = self.request.data
        food_id = data.get("id", None)
        quantity = data.get("quantity", None)
        size = data.get("size", None)
        if not (food_id and quantity and size):
            return Response(
                {"detail": "no_id_provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            food = Food.objects.get(pk=food_id)
            if food and food.is_available:
                if not size in food.prices:
                    size = food.min_price
                if not quantity:
                    quantity = 1
                # handling both create and update
                CartItem.objects.filter(cart=cart, food=food).update(
                    quantity=quantity,
                    price=size,
                )
                return Response(status=status.HTTP_200_OK)

            else:
                return Response(
                    {"detail": "food_does_not_exist"}, status=status.HTTP_404_NOT_FOUND
                )
        except Food.DoesNotExist:
            return Response(
                {"detail": "food_does_not_exist"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(e)
            return Response(
                {"detail": "unknown_error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, *args, **kwargs):
        """provides deleting a cart item or clearing cart"""
        item_id = self.request.data.get("item-id", None)
        if item_id:
            try:
                cart_id = self.request.user.cart.id
                item = CartItem.objects.filter(id=item_id, cart__id=cart_id).first()
                if item:
                    item.delete()
                    return Response(
                        {"message": "item_deleted"}, status=status.HTTP_204_NO_CONTENT
                    )
                else:
                    Response(
                        {"detail": "no_matching_item"}, status=status.HTTP_404_NOT_FOUND
                    )
            except:
                return Response(status=status.HTTP_400_BAD_REQUEST)
        # clearing cart
        else:
            self.request.user.cart.clear()
            return Response(
                {"message": "cart_cleared"}, status=status.HTTP_204_NO_CONTENT
            )

    def post(self, *args, **kwargs):
        """Adding new item into cart"""
        cart = self.request.user.cart
        data = self.request.data
        food_id = data.get("id", None)
        quantity = data.get("quantity", None)
        size = data.get("size", None)
        if not (food_id and quantity and size):
            return Response(
                {"detail": "no_id_provided"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            food = Food.objects.get(pk=food_id)
            if food and food.is_available:
                # replacing cart vendor with new vendor
                if not cart.is_empty() and cart.get_vendor() != food.vendor:
                    cart.clear()

                if not size in food.prices:
                    size = food.min_price
                if not quantity:
                    quantity = 1
                # handling both create and update
                CartItem.objects.update_or_create(
                    cart=cart,
                    food=food,
                    price=size,
                    defaults={"quantity": quantity},
                )
                return Response(
                    {"cart_count": cart.calculate_total_items()},
                    status=status.HTTP_200_OK,
                )

            else:
                return Response(
                    {"detail": "food_does_not_exist"}, status=status.HTTP_404_NOT_FOUND
                )
        except Food.DoesNotExist:
            return Response(
                {"detail": "food_does_not_exist"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            print(e)
            return Response(
                {"detail": "unknown_error"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
