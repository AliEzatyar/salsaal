import json
import weasyprint
from django.template.loader import render_to_string
from django.conf import settings
from io import BytesIO
from django.http import FileResponse
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType

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
    UserProfileSerializer,
)
from accounts.models import CUSTOMER, SHOP, User
from accounts.utils import send_email, send_forgot_email
from order.models import Order, OrderItem
from order.serializers import OrderItemSerializer, OrderSerializer
from cart.models import CartItem
from cart.serializers import CartSerializer
from marketplace.models import Product, Rating
from vendor.models import Vendor
from vendor.serializers import VendorSerializer
from marketplace.serializers import CProductSerializer, VProductSerializer ,RatingSerializer
from api.backends import ProductFilterSet
from api.permissions import IsVendorOfProduct

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
        return Response({"saved": True}, status=status.HTTP_200_OK)

    def get_queryset(self):
        """overrding it to get orders of specific user"""
        user_id = self.request.user.id
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
        # sending pdf file
        buffer = BytesIO()
        html = render_to_string("order/payment.html", {"order": order})
        weasyprint.HTML(string=html).write_pdf(
            buffer,
            stylesheets=[
                weasyprint.CSS(settings.STATICFILES_DIRS[0] + "css/payment.css")
            ],
        )
        response = FileResponse(
            buffer,
            as_attachment=True,
                                                                                                                                                                                                                                      )
        response["Content-Disposition"] = "attachment;"+f" filename=order_{order.user.first_name}_{order.id}.pdf"
        

        return response

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['user'] = self.request.user.id
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


"""Marketplace API Views"""


class ProductReadViewSet(viewsets.ReadOnlyModelViewSet):
    """this view only handles representation of products to normal users"""

    queryset = Product.objects.filter(is_available=True)
    serializer_class = CProductSerializer
    permission_classes = [permissions.AllowAny]
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "price"]
    ordering = ["price"]
    # filering
    filterset_class = ProductFilterSet
    # searching
    search_fields = ["name", "category__name", "description"]


class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.filter(enabled=True)
    serializer_class = RatingSerializer
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["created_at", "rating"]
    ordering = ["created_at"]

    def get_queryset(self):
        """overriding in order to distinguish by vendor or product"""
        object_id = self.request.query_params.get("obj_id", None)
        query_set = self.queryset
        if object_id:
            query_set = self.queryset.filter(object_id=int(object_id))
        return query_set

    def create(self, request, *args, **kwargs):
        rating_type = request.query_params.get("type")
        obj_id = request.query_params.get("obj_id")
        if not rating_type or not obj_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        data = request.data
        previous = Rating.objects.filter(
            object_id=int(obj_id), user=request.user
        ).first()
        # handling indirect update
        if previous:
            # prviously exists, performing update
            previous.comment = data["comment"]
            previous.rating = data["rating"]
            previous.enabled = True
            previous.save()
            return Response({"updated": True}, status=status.HTTP_200_OK)

        else:
            # performing new rating creation
            serializer = self.get_serializer(data=data)
            try:
                serializer.is_valid(raise_exception=True)
            except:
                return Response(
                    {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
                )
            self.perform_create(
                serializer
            )  # sets instance to serializer after creation
            instance = serializer.instance
            if rating_type == "vendor":
                instance.content_type = ContentType.objects.get_for_model(Vendor)
            elif rating_type == "product":
                instance.content_type = ContentType.objects.get_for_model(Product)
            instance.object_id = int(obj_id)
            instance.enabled = True
            instance.save()
            # successfull creation
            return Response(serializer.data, status=status.HTTP_201_CREATED)


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
        items = data["items"]
        for item_id, quantity in items:
            item = CartItem.objects.filter(id=item_id).first()
            if item and item.product.existing_amount > int(quantity):
                item.quantity = quantity
                item.save()
            else:
                continue
        # successful edit
        cart = self.request.user.cart
        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, *args, **kwargs):
        """deleting a cart item"""
        item = self.request.data["item-id"]
        item = CartItem.objects.filter(id=item).first()
        product = item.product
        product.existing_amount += item.quantity
        product.save()
        item.delete()
        return Response(status=status.HTTP_200_OK)

    def post(self, *args, **kwargs):
        """overriding for adding new item to cart"""
        cart = self.request.user.cart
        product_id = self.request.data["product-id"]
        product = Product.objects.filter(pk=product_id).first()
        if product and product.existing_amount > 0:
            state = CartItem.objects.get_or_create(cart=cart, product=product)
            if state[1]:
                # if item is created now and added
                product.existing_amount -= 1
                cart_item = state[0]
                # cart_item.save()
                cart.items.add(cart_item)
            return Response(status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "not_existing"}, status=status.HTTP_400_BAD_REQUEST
            )


"""Vendor API Views"""


class VendorAPIView(views.APIView):

    def get(self, *args, **kwargs):
        """returns all vendor details"""
        role = self.request.user.role
        if role == 2 or not hasattr(self.request.user, "vendor"):
            # a normal user is not allowed
            return Response(
                {"error": "user_not_a_vendor"}, status=status.HTTP_400_BAD_REQUEST
            )
        vendor = self.request.user.vendor
        serializer = VendorSerializer(vendor)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, *args, **kwargs):
        """enables vendor and related userprofile update"""
        role = self.request.user.role
        if role == 2:
            # a normal user is not allowed
            return Response(
                {"error": "user_not_a_vendor"}, status=status.HTTP_400_BAD_REQUEST
            )
        data = self.request.data
        vendor = self.request.user.vendor
        vendor_serializer = VendorSerializer(vendor, data=data, partial=True)

        # validation
        try:
            vendor_serializer.is_valid(raise_exception=True)
        except:
            return Response(
                {"errors": vendor_serializer.errors}, status=status.HTTP_400_BAD_REQUEST
            )

        vendor_serializer.save()
        # success
        return Response(vendor_serializer.data, status=status.HTTP_200_OK)

    def post(self, *args, **kwargs):
        """overriden for converting to vendor"""
        data = self.request.data
        user = self.request.user
        profile = user.profile
        vendor = Vendor(user=user, user_profile=profile)
        vendor.vendor_name = data["vendor_name"]
        vendor.save()
        user.role = SHOP
        user.save()
        return Response(status=status.HTTP_201_CREATED)

    def delete(self, *args, **kwargs):
        """overriden to cancel vendor account"""
        user = self.request.user
        vendor = user.vendor
        user.role = CUSTOMER
        vendor.delete()
        user.save()
        return Response(status=status.HTTP_200_OK)


"""Product Management API Views"""


class VendorProductsManageViewSet(viewsets.ModelViewSet):
    """this class enables CRUD operations on products of a vendor"""

    queryset = Product.objects.all()
    serializer_class = VProductSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOfProduct]
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["-created_at"]
    # filering
    filterset_class = ProductFilterSet
    # searching
    search_fields = ["name", "category__name", "description"]

    def get_queryset(self):
        """any queryset should be of the requesting vendor"""
        query_set = self.queryset.filter(vendor__user__id=self.request.user.id)
        return query_set

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["vendor"] = self.request.user.vendor.id
        return context
