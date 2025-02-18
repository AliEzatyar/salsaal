from django.shortcuts import render
from django.contrib.auth.decorators import login_required,user_passes_test
from .models import Order, OrderItem
from django.shortcuts import redirect
from cart.models import CartItem
from  accounts.utils import  user_test


@login_required
def create_order(request):
    """this view creates an order and represents to user"""
    user = request.user
    user_profile = user.profile
    order = Order.objects.get_or_create(
        user=user,status=0
    )[0]

    if not hasattr(request.user, "cart"):
        return redirect("main:home")
    cart = user.cart
    order_items = []
    OrderItem.objects.filter(order=order).delete() # flush previous items and recreate new items
    for item in CartItem.objects.filter(cart=cart).select_related("product__vendor"):
        order_item = OrderItem.objects.get_or_create(
            order=order,
            product=item.product,
            vendor=item.product.vendor,
            quantity=item.quantity,
            price=item.product.price,
        )[0]
        order_items.append(order_item)
    order.calculate_total_price()
    
    return render(
        request,
        "order/create_order.html",
        context=locals(),
    )


@login_required
@user_passes_test(user_test)
def list_orders(request):
    orders = Order.objects.filter(user=request.user)
    return render(request,"customer/customer_orders.html",context=locals()) 