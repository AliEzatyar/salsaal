from rest_framework import generics
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from vendor.models import Vendor
from .serializers import (
    UserCreationSerializer,
    UserDetailSerializer,
    VendorCreateSerializer,
    VendorManageSerializer,
)
import json
from django.http.response import JsonResponse
from ..models import SHOP, User
from ..utils import send_email, send_forgot_email
from rest_framework import permissions
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator


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
        return JsonResponse({"ERROR": "REQUEST HAS NO DATA"})

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
        return JsonResponse({"DONE": True})

    # errors with the serializer
    return JsonResponse(
        {
            "ERRORS": [
                user_ser.errors if not a else None,
                vendor_ser.errors if not b else None,
            ]
        }
    )


@api_view(["GET", "PUT", "DELETE", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
def manage_vendor(request):
    if request.method == "GET":
        # retrive the object
        vendor = Vendor.objects.filter(user=request.user).first()
        if vendor:
            ser = VendorManageSerializer(instance=vendor)
            return JsonResponse({"DONE": True, "data": ser.data})
        return JsonResponse({"ERROR": "user has no registered shop"})

    elif request.method == "DELETE":
        # delete the object
        vendor = Vendor.objects.filter(user=request.user).first()
        vendor.delete()
        return JsonResponse({"DONE": True})

    elif request.method == "PATCH":
        # partial update the object
        data = request.data
        vendor = Vendor.objects.filter(user=request.user).first()
        if vendor:
            ser = VendorManageSerializer(instance=vendor, data=data, partial=True)
            if ser.is_valid():
                ser.save()
                return JsonResponse({"DONE": True})
            else:
                return JsonResponse({"ERROR": ser.errors})

        return JsonResponse({"ERROR": "user has no registered shop"})


@api_view(["POST"])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def forgot_password(request):
    data = request.data
    email = data.get("email", None)
    # if there is no email provided
    if email in ("None", None):
        return JsonResponse({"ERROR": "Email is required"})

    user = User.objects.filter(email=email).first()

    # no user regesetered with that email
    if not user:
        return JsonResponse({"ERROR": "No user registered with this email."})

    # sending the reset token
    send_forgot_email(request, user)
    # success
    return JsonResponse({"DONE": True})

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
        return JsonResponse({"ERROR": "Token and uid are required."})
    try:
        # finding the user
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.filter(pk=user_id).first()

    except (TypeError, ValueError, OverflowError):
        user = None

    if user and default_token_generator.check_token(user, data["token"]):
        request.session["uid"] = user_id
        return JsonResponse({"MESSAGE": "token is valid"})
    return JsonResponse({"ERROR": "token invalid"})
