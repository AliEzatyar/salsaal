import json
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Order, OrderItem, ORDER_STATUS_CHOICES
from django.shortcuts import redirect
from cart.models import CartItem
from accounts.utils import user_test
import weasyprint
from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from .serializers import OrderSerializer, OrderItemSerializer, Order
from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework import views
from rest_framework import status
from rest_framework.response import Response

"""Order API Views"""


class OrderViewSet(viewsets.ModelViewSet):
    """this view enables order create/edit/del by customer"""

    serializer_class = OrderSerializer

    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        order.cancel_order()
        return Response(status=status.HTTP_200_OK)

    def get_queryset(self):
        """overrding it to get orders of specific user"""
        user_id = self.request.user.id
        new_queryset = Order.objects.filter(user_id=int(user_id))
        return new_queryset

    def create(self, request, *args, **kwargs):
        """overriding this method to create order items from cart and calc totals"""
        data = dict(
            request.data
        )  # auto json to dict since restframework request object
        cart = request.user.cart
        # setting vendor id
        if cart.calculate_total_items() < 1:
            return Response(
                {"error": "no item in cart"}, status=status.HTTP_400_BAD_REQUEST
            )
        vendor_id = CartItem.objects.filter(cart=cart).first().food.vendor.id
        data["vendor"] = vendor_id

        # creating the serializer
        serializer = self.get_serializer(data=data)
        
        if Order.objects.filter(
            user=request.user, status=ORDER_STATUS_CHOICES[1][1]
        ).exists():
            # prevent duplicate order if user has one 'waiting' order already
            return Response(
                {"error": "order already in process"}, status=status.HTTP_403_FORBIDDEN
            )

        serializer.is_valid(raise_exception=True)  # validating data
        self.perform_create(serializer)  # creating the order
        order = serializer.instance  # getting newly created order object by serializer
        order_items = []
        OrderItem.objects.filter(
            order=order
        ).delete()  # flush previous items and recreate new items

        # creating order item objects
        for item in CartItem.objects.filter(cart=cart).select_related("food__vendor"):
            order_item = OrderItem.objects.get_or_create(
                order=order,
                food=item.food,
                vendor=item.food.vendor,
                quantity=item.quantity,
                price=item.food.min_price,
            )[0]
            order_items.append(order_item)
        order.calculate_total_price()  # setting total price field value
        order.set_total_items()  # setting total items amount field value

        # flushing the cart
        cart.items.all().delete()
        
        response = Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )
        return response

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["user"] = self.request.user.id
        return context


class OrderItemListAPIView(views.APIView):

    def get(self, request, order_id):
        items = OrderItem.objects.filter(order_id=order_id)
        serializer = OrderItemSerializer(items, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OrderItemDetailAPIView(views.APIView):
    def get(self, request, item_id):
        item = OrderItem.objects.filter(id=item_id).first()
        if item:
            serializer = OrderItemSerializer(item)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(
            {"message": "no_object_found"}, status=status.HTTP_404_NOT_FOUND
        )


@login_required
def create_order(request):
    """this view creates an order and represents to user"""
    user = request.user
    user_profile = user.profile
    order = Order.objects.filter(user=user, status=ORDER_STATUS_CHOICES[1][1]).first()
    if not order:
        Order.objects.create(user=user, status=ORDER_STATUS_CHOICES[1][1])

    if not hasattr(request.user, "cart"):
        return redirect("main:home")
    cart = user.cart
    order_items = []
    OrderItem.objects.filter(
        order=order
    ).delete()  # flush previous items and recreate new items
    for item in CartItem.objects.filter(cart=cart).select_related("food__vendor"):
        order_item = OrderItem.objects.get_or_create(
            order=order,
            food=item.food,
            vendor=item.food.vendor,
            quantity=item.quantity,
            price=item.food.min_price,
        )[0]
        order_items.append(order_item)
    order.calculate_total_price()
    order.set_total_items()

    # sending pdf file
    html = render_to_string("order/payment.html", {"order": order})
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f"filename=order_{order.user.first_name}_{order.id}.pdf"
    )
    weasyprint.HTML(string=html).write_pdf(
        response,
        stylesheets=[weasyprint.CSS(settings.STATICFILES_DIRS[0] + "css/payment.css")],
    )
    return response
    #     return render(
    #     request,
    #     "order/create_order.html",
    #     context=locals(),
    # )


@login_required
@user_passes_test(user_test)
def list_orders(request):
    """this view provides all orders of a customer"""
    orders = Order.objects.filter(user=request.user)
    return render(request, "customer/customer_orders.html", context=locals())


@login_required
@user_passes_test(user_test)
def cancel_order(request):
    data = json.loads(request.body)
    order_id = data["id"]
    order = Order.objects.filter(user=request.user, id=order_id).first()
    if order:
        order.cancel_order()
        return JsonResponse({"saved": True})
    else:
        return JsonResponse({"saved": False})
