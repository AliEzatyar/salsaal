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
from marketplace.models import Food, Rating
from vendor.models import Vendor
from vendor.serializers import VendorSerializer
from marketplace.serializers import FoodSerializer, RatingSerializer
from api.backends import FoodFilterSet
from api.permissions import IsVendorOfFood
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D


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
        for item in CartItem.objects.filter(cart=cart).select_related("food__vendor"):
            order_item = OrderItem.objects.get_or_create(
                order=order,
                food=item.food,
                vendor=item.food.vendor,
                quantity=item.quantity,
                price=item.food.price,
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
        response["Content-Disposition"] = (
            "attachment;" + f" filename=order_{order.user.first_name}_{order.id}.pdf"
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


"""Marketplace API Views"""


class FoodReadViewSet(viewsets.ReadOnlyModelViewSet):
    """this view only handles representation of foods to normal users"""

    queryset = Food.objects.filter(is_available=True)
    serializer_class = FoodSerializer
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
    filterset_class = FoodFilterSet
    # searching
    search_fields = ["name", "category__name", "description", "vendor__vendor_name"]


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
        """overriding in order to distinguish by vendor or food"""
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
            elif rating_type == "food":
                instance.content_type = ContentType.objects.get_for_model(Food)
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
            if item and item.food.is_available:
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


"""Food Management API Views"""


class VendorFoodsManageViewSet(viewsets.ModelViewSet):
    """this class enables CRUD operations on foods of a vendor"""

    queryset = Food.objects.all()
    serializer_class = FoodSerializer
    permission_classes = [permissions.IsAuthenticated, IsVendorOfFood]
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "price", "created_at"]
    ordering = ["-created_at"]
    # filering
    filterset_class = FoodFilterSet
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


"""Advanced search"""


class SearchApiView(views.APIView):
    """This api view handles searching for both food and vendor objects considering distance"""

    def get(self, *args, **kwargs):
        query = self.request.query_params.get("query", None)
        log = self.request.query_params.get("long", None)
        lat = self.request.query_params.get("lat", None)
        max_distance = self.request.query_params.get("max_distance", 5)

        # determinig user location
        try:
            if lat and log:
                user_location = Point(float(log), float(lat), srid=4326)
            else:
                user_location = self.request.user.profile.location
        except:
            Response(
                {"error": "invalid location data"}, status=status.HTTP_400_BAD_REQUEST
            )
            
        # handling empty query
        if not query or not query.strip():
            return Response(
                {"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # search for foods
        foods = Food.objects.filter(
            name__icontains=query, is_available=True
        ).select_related("vendor__user_profile")

        foods = foods.annotate(
            distance=Distance("vendor__user_profile__location", user_location)
        )
        # limiting distance
        foods = foods.filter(distance__lte=D(km=max_distance))
        foods_serializer = FoodSerializer(foods, many=True)

        # vendors found by query and limiting distance
        vendors = (
            Vendor.objects.filter(
                vendor_name__icontains=query, is_approved=True, user__is_active=True
            )
            .annotate(distance=Distance("user_profile__location", user_location))
            .filter(distance__lte=D(km=max_distance))
        )
        # preparing as json
        vendors_serializer = VendorSerializer(vendors, many=True)
        total_found = len(vendors) + len(foods)
        # success
        return Response(
            {
                "total": total_found,
                "foods": foods_serializer.data,
                "vendors": vendors_serializer.data,
            },
            status=status.HTTP_200_OK,
        )
