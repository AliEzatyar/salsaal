from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from rest_framework import generics, filters
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from rest_framework import permissions
from rest_framework import viewsets, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django_filters.rest_framework import DjangoFilterBackend

from accounts.serializers import (
    UserCreationSerializer,
    UserDetailSerializer,
    VendorCreateSerializer,
    VendorManageSerializer,
)
from accounts.models import SHOP, User
from accounts.utils import send_email, send_forgot_email
from order.models import Order, OrderItem
from order.serializers import OrderItemSerializer, OrderSerializer
from cart.models import Cart, CartItem
from marketplace.models import Product
from marketplace.serializers import ProductSerializer
from vendor.models import Vendor
from marketplace.serializers import ProductSerializer
from api.backends import ProductFilterSet

"""Account API Views"""


class RegisterUser(generics.CreateAPIView):
    serializer_class = UserCreationSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        # sending the email
        send_email(self.request, user)


class UpdateDeleteRetriveUser(generics.RetrieveUpdateDestroyAPIView):
    """
    it works with 4 methods:
    GET --> retrieve user data
    PUT --> update user
    DELETE> delete the user account itself
    NOTE: this view uses default authentication class which need JWT-token
    for every request
    """

    serializer_class = UserDetailSerializer
    queryset = User.objects.all()

    def get_object(self):
        """this ensures that only the user itself works on its account"""
        return self.request.user


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def register_vendor(request):
    # converting binary to dictionary using json since type was json
    if request.body in ("None", None):
        return Response(
            {"ERROR": "REQUEST HAS NO DATA"}, status=status.HTTP_400_BAD_REQUEST
        )

    data = request.data
    user_ser = UserCreationSerializer(data=data["user"])
    vendor_ser = VendorCreateSerializer(data=data)
    a, b = user_ser.is_valid(), vendor_ser.is_valid()
    # if both serializers are valid
    if a and b:
        # saving the use
        user = User(**user_ser.validated_data)
        user.role = SHOP
        user.is_active = True
        user.set_password(user.password)
        user.save()
        # saving the vendor
        vendor = Vendor(**vendor_ser.validated_data)
        vendor.user_profile = user.profile
        vendor.user = user
        vendor.save()
        # sending the email to activate the account
        send_email(request, user)
        # success
        return Response({"DONE": True}, status=status.HTTP_200_OK)

    # serializers not valid
    return Response(
        {
            "ERRORS": [
                user_ser.errors if not a else None,
                vendor_ser.errors if not b else None,
            ]
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["GET", "PUT", "DELETE", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def manage_vendor(request):
    if request.method == "GET":
        # retrive the object
        vendor = Vendor.objects.filter(user=request.user).first()
        if vendor:
            ser = VendorManageSerializer(instance=vendor)
            return Response({"DONE": True, "data": ser.data}, status=status.HTTP_200_OK)
        return Response(
            {"ERROR": "user has no registered shop"}, status=status.HTTP_400_BAD_REQUEST
        )

    elif request.method == "DELETE":
        # delete the object
        vendor = Vendor.objects.filter(user=request.user).first()
        vendor.delete()
        return Response({"DONE": True}, status=status.HTTP_200_OK)

    elif request.method == "PATCH":
        # partial update the object
        data = request.data
        vendor = Vendor.objects.filter(user=request.user).first()
        if vendor:
            ser = VendorManageSerializer(instance=vendor, data=data, partial=True)
            if ser.is_valid():
                ser.save()
                return Response({"DONE": True}, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"ERROR": ser.errors}, status=status.HTTP_400_BAD_REQUEST
                )

        return Response(
            {"ERROR": "user has no registered shop"}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def forgot_password(request):
    data = request.data
    email = data.get("email", None)
    # if there is no email provided
    if email in ("None", None):
        return Response(
            {"ERROR": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.filter(email=email).first()

    # no user regesetered with that email
    if not user:
        return Response(
            {"ERROR": "No user registered with this email."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # sending the reset token
    send_forgot_email(request, user)
    # success
    return Response(status=status.HTTP_200_OK)


# not used
@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def validate_token(request):
    """
    this view is not used for now, we should enable universall link in order to redirect
    the user to app and call this endpoint; for now, we just set the reset link for
    the browser and do it all there.
    """
    data = request.data
    uid = data.get("uidb64", None)
    token = data.get("token", None)
    if not uid or not token:
        return Response(
            {"ERROR": "Token and uid are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        # finding the user
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.filter(pk=user_id).first()

    except (TypeError, ValueError, OverflowError):
        user = None

    if user and default_token_generator.check_token(user, data["token"]):
        request.session["uid"] = user_id
        return Response({"MESSAGE": "token is valid"}, status=status.HTTP_200_OK)
    return Response({"ERROR": "token invalid"}, status=status.HTTP_400_BAD_REQUEST)


"""Order API Views"""

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer

    @action(detail=True, methods=["patch"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        order.cancel_order()
        return Response({"saved": True},status=status.HTTP_200_OK)

    def get_queryset(self):
        """overrding it to get orders of specific user"""
        user_id = self.request.query_params['user_id']
        new_queryset = self.queryset.filter(user_id=int(user_id)) 
        return new_queryset
    
    
    

    def create(self, request, *args, **kwargs):
        """overriding this method to create order items from cart and calc totals"""
        data = request.data  # auto json to dict since restframework request object
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)  # validating data
        self.perform_create(serializer)  # creating the order
        order = serializer.instance  # getting newly created order object by serializer
        cart = request.user.cart
        order_items = []
        OrderItem.objects.filter(
            order=order
        ).delete()  # flush previous items and recreate new items
        # creating order item objects
        for item in CartItem.objects.filter(cart=cart).select_related(
            "product__vendor"
        ):
            order_item = OrderItem.objects.get_or_create(
                order=order,
                product=item.product,
                vendor=item.product.vendor,
                quantity=item.quantity,
                price=item.product.price,
            )[0]
            order_items.append(order_item)
        order.calculate_total_price()  # setting total price field value
        order.set_total_items()  # setting total items amount field value
        return Response(serializer.data, status=status.HTTP_201_CREATED)


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


"""Marketplace API Views"""

class ProductReadViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(is_available=True)
    serializer_class = ProductSerializer
    # ordering
    filter_backends = [filters.OrderingFilter, filters.SearchFilter, DjangoFilterBackend]
    ordering_fields = ['name','price']
    ordering = ['price']
    # filering
    filterset_class = ProductFilterSet
    # searching
    search_fields = ['name','category__name','description']
    
    
    