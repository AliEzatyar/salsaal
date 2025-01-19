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
from rest_framework import permissions, authentication
from django.contrib.auth.decorators import user_passes_test


class RegisterUser(generics.CreateAPIView):
    serializer_class = UserCreationSerializer
    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]


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

    data = json.loads(request.body)
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
        data = json.loads(request.body)
        vendor = Vendor.objects.filter(user=request.user).first()
        if vendor:
            ser = VendorManageSerializer(instance=vendor, data=data, partial=True)
            if ser.is_valid():
                ser.save()
                return JsonResponse({"DONE": True})
            else:
                return JsonResponse({"ERROR": ser.errors})

        return JsonResponse({"ERROR": "user has no registered shop"})
