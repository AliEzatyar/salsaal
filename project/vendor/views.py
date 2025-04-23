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
    http_method_names = ["get","patch","delete"]
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


def become_seller(request):
    """this view presents seller account creation info"""
    if request.user.is_authenticated and request.user.role == 1:
        return redirect("accounts:dashboard")
    return render(request, "vendor/become_seller.html")


@login_required
def register_vendor(request):
    """this view registers a new vendor using vendor form and user profile form"""
    # POST
    if request.method == "POST":
        # we pass instance since profiles are automatically created when user account is created
        profile_form = UserProfileForm(
            request.POST, instance=request.user.profile, files=request.FILES
        )
        vendor_form = VendorRegForm(request.POST, files=request.FILES)
        # both forms are valid
        if profile_form.is_valid() and vendor_form.is_valid():
            profile = profile_form.save(commit=False)
            request.user.role = SHOP
            with atomic():
                request.user.save()
                # registering the shop
                vendor = vendor_form.save(commit=False)
                vendor.user = request.user
                profile.save()
                vendor.user_profile = profile
                vendor.save()
                messages.success(
                    request,
                    message="اطلاعات شما ثبت گردید. تیم ما به زودی اسناد شما را بررسی و جواب آن را ذربعه ایمیل برایتان ارسال خواهند کرد.",
                )
                # job done
                return redirect(reverse("accounts:dashboard"))

        # forms have got errors
        else:
            messages.error(request, message="فورم پر شده دارای بعضی مشکلات است.")
            print(vendor_form.errors, "\n\n", profile_form.errors, "")
            return render(
                request,
                "vendor/register-vendor.html",
                {"profile_form": profile_form, "vendor_form": vendor_form},
            )

    # GET
    vendor_form = VendorRegForm()
    profile_form = UserProfileForm()
    if request.user.role == 1:
        return redirect("accounts:dashboard")

    return render(
        request,
        "vendor/register-vendor.html",
        {"profile_form": profile_form, "vendor_form": vendor_form},
    )


@login_required
@user_passes_test(vendor_tester)
def vendor_profile(request):
    """this view enables vendors to update their user profile and update licence"""
    vendor = request.user.vendor
    vendor_user_profile = UserProfile.objects.filter(user=request.user).first()
    # in POST
    if request.method == "POST":
        vendor_user_profile_form = UserProfileForm(
            instance=vendor_user_profile, data=request.POST, files=request.FILES
        )

        vendor_form = VendorForm(
            instance=vendor, data=request.POST, files=request.FILES
        )
        if vendor_user_profile_form.is_valid() and vendor_form.is_valid():
            vendor_user_profile_form.save()
            vendor_form.save()
            messages.success(request, "پروفایل شما تغییر یافت.")
            return redirect("vendor:vendor_profile_edit")
        # there were errros
        messages.error(request, "خطا در تغییر پروفایل!")
        return render(
            request,
            "vendor/vendor_profile.html",
            {
                "vendor_form": vendor_form,
                "profile_form": vendor_user_profile_form,
                "profile": vendor_user_profile,
            },
        )
    # in GET
    else:
        if vendor not in (None, "None") and vendor_user_profile:
            # both forms being shown to vendor
            vendor_user_profile_form = UserProfileForm(instance=vendor_user_profile)
            vendor_form = VendorForm(instance=vendor)
            return render(
                request,
                "vendor/vendor_profile.html",
                {
                    "vendor_form": vendor_form,
                    "profile_form": vendor_user_profile_form,
                    "profile": vendor_user_profile,
                },
            )
        return HttpResponse("شما اجازه دسترسی به این صفحه را ندارید.")


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


@login_required
@user_passes_test(vendor_tester)
def add_food(request):
    # POST
    if request.method == "POST":
        form = FoodForm(request.POST, files=request.FILES)
        if form.is_valid():
            try:
                food = form.save(commit=False)
                category_id = food.category.id
                food.vendor = request.user.vendor
                food.save()
                # successfull
                messages.success(request, "غذا موفقانه ثبت شد")
                return redirect("vendor:vendor_foods")
            except Exception as e:
                messages.error(request, "خطا در ثبت غذا!")

                return render(request, "vendor/add_food.html", context=locals())
        # there are form errors
        messages.error(request, "خطا در ثبت غذا!")
        return render(request, "vendor/add_food.html", context=locals())
    # GET
    form = FoodForm()
    return render(request, "vendor/add_food.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def edit_food(request, id):
    """this view enables a vendor to modify and existing food"""
    food = Food.objects.filter(id=id, vendor=request.user.vendor).first()
    if not food:
        # redirect the vendor back to catalog builder if no such food
        messages.error(request, "چنین غذای وجود ندارد!")
        return redirect("vendor:vendor_foods")

    # POST
    if request.method == "POST":
        form = FoodForm(request.POST, instance=food, files=request.FILES)
        if form.is_valid():
            form.save()
            # successful
            messages.success(request, "جزییات غذا تغییر یافت")
            return redirect("vendor:vendor_foods")

        # there are form errors
        messages.error(request, "در جریان ثبت تغییرات مشکلی بوجود آمد!")
        return render(request, "vendor/edit_food.html", context=locals())

    # GET
    form = FoodForm(instance=food)
    return render(request, "vendor/edit_food.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def delete_food(request, id):
    """this view enables a vendor to delete a food"""
    food = Food.objects.filter(id=id, vendor=request.user.vendor).first()
    if food:
        food.delete()
        messages.success(request, "غذا موفقانه حذف گردید.")
        return redirect("vendor:vendor_foods")
    else:
        messages.error(request, "چنین غذای وجود ندارد!")
    return redirect("vendor:vendor_foods")
