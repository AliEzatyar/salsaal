from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from accounts.models import SHOP, UserProfile
from accounts.utils import send_otp, user_test
from marketplace.models import Category, Food, Rating
from carrier.permissions import IsVendor
from vendor.forms import FoodForm, VendorForm
from vendor.models import Vendor
from accounts.forms import UserProfileForm, UserRegForm, VendorRegForm
from django.contrib import messages
from django.urls import reverse
from .utils import get_vendor, vendor_tester
from django.db.transaction import atomic
from django.db.models.aggregates import Count
from collections import Counter
from accounts.models import CUSTOMER
from .serializers import VendorSerializerDetailed
from marketplace.serializers import FoodSerializerDetail
from api.permissions import IsVendorOfFood
from rest_framework.decorators import action
from rest_framework import permissions
from rest_framework import viewsets
from rest_framework import views
from rest_framework import status
from rest_framework.response import Response
from rest_framework import filters
from django_filters.rest_framework import DjangoFilterBackend
from api.backends import FoodFilterSet

# Create your views here.


"""Vendor API Views"""


class VendorAPIView(views.APIView):
    permission_classes = [permissions.IsAuthenticated, IsVendor]
    http_method_names = ["get", "patch", "delete"]

    def get(self, *args, **kwargs):
        """returns all vendor details"""
        vendor = self.request.user.vendor
        serializer = VendorSerializerDetailed(vendor)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, *args, **kwargs):
        """enables vendor and related userprofile update"""
        data = self.request.data
        vendor = self.request.user.vendor
        vendor_serializer = VendorSerializerDetailed(vendor, data=data, partial=True)
        vendor_serializer.is_valid(raise_exception=True)
        vendor_serializer.save()
        # success
        return Response(vendor_serializer.data, status=status.HTTP_200_OK)

    def delete(self, *args, **kwargs):
        """overriden to cancel vendor account"""
        user = self.request.user
        vendor = user.vendor
        user.role = CUSTOMER
        vendor.delete()
        user.save()
        return Response(status=status.HTTP_200_OK)


class ConvertToVendorAPIView(views.APIView):
    http_method_names = ["post"]

    def post(self, *args, **kwargs):
        """
        THis method converts a user to a vendor account
        body: vendor_name
        """
        # if user is already a vendor
        if self.request.user.role == SHOP or hasattr(self.request.user, "vendor"):
            return Response(
                {"error": "user already a vendor"}, status=status.HTTP_403_FORBIDDEN
            )

        data = self.request.data
        ser = VendorSerializerDetailed(data=data, context={"request": self.request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data, status=status.HTTP_201_CREATED)


"""Food Management API Views"""


class VendorFoodsManageViewSet(viewsets.ModelViewSet):
    """this class enables CRUD operations on foods of a vendor"""

    queryset = Food.objects.all()
    serializer_class = FoodSerializerDetail
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




def vendor_details(request, vendor_name):
    """public accessible view to show details of a vendor"""
    vendor = Vendor.objects.filter(vendor_name=vendor_name).first()
    if not vendor:
        return HttpResponse("حساب فروشنده با این نام موجود نیست!")
    vendor_foods = Food.objects.filter(vendor=vendor)
    categories = [pro.category.name for pro in vendor_foods]
    ratings = Rating.objects.filter(object_id=vendor.id)
    cat_count_pro = Counter(categories).items()
    foods_count = vendor_foods.count()

    return render(request, "vendor/vendor_details.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def vendor_dashboard(request):
    """this view represents sales page for a vendor"""
    vendor = Vendor.objects.get(user=request.user)
    return render(request, "vendor/vendor_dashboard.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def vendor_foods(request):
    """this view presents vendor's foods with details enables CRUD for foods"""
    foods = Food.objects.filter(vendor=get_vendor(request))
    return render(request, "vendor/vendor_foods.html", context=locals())
