from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from accounts.models import SHOP, UserProfile
from accounts.utils import send_email, user_test
from marketplace.models import Category, Product
from vendor.forms import ProductForm, VendorForm
from vendor.models import Vendor
from accounts.forms import UserProfileForm, UserRegForm, VendorRegForm
from django.contrib import messages
from django.utils.text import slugify
from django.urls import reverse
from .utils import get_vendor, vendor_tester
from django.db.transaction import atomic
from django.db.models.aggregates import Count
from collections import Counter
# Create your views here.


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
    """this view enables vendors to update their user profile and update licience"""
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
    vendor_products = Product.objects.filter(vendor=vendor)
    categories = [pro.category.name for pro in vendor_products]
    cat_count_pro = Counter(categories).items()
    products_count = vendor_products.count()
    return render(request, "vendor/vendor_details.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def vendor_dashboard(request):
    """this view represents sales page for a vendor"""
    vendor = Vendor.objects.get(user=request.user)
    return render(request, "vendor/vendor_dashboard.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def vendor_products(request):
    """this view presents vendor's products with details enables CRUD for products"""
    products = Product.objects.filter(vendor=get_vendor(request))
    return render(request, "vendor/vendor_products.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def add_product(request):
    # POST
    if request.method == "POST":
        form = ProductForm(request.POST, files=request.FILES)
        if form.is_valid():
            try:
                product = form.save(commit=False)
                category_id = product.category.id
                product.vendor = request.user.vendor
                product.save()
                # successfull
                messages.success(request, "محصول موفقانه ثبت شد")
                return redirect("vendor:vendor_products")
            except Exception as e:
                messages.error(request, "خطا در ثبت محصول!")
                return render(request, "vendor/add_product.html", context=locals())
        # there are form errors
        messages.error(request, "خطا در ثبت محصول!")
        return render(request, "vendor/add_product.html", context=locals())
    # GET
    form = ProductForm()
    return render(request, "vendor/add_product.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def edit_product(request, id):
    """this view enables a vendor to modify and existing product"""
    product = Product.objects.filter(id=id, vendor=request.user.vendor).first()
    if not product:
        # redirect the vendor back to catalog builder if no such product
        messages.error(request, "چنین محصولی وجود ندارد!")
        return redirect("vendor:vendor_products")

    # POST
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product, files=request.FILES)
        if form.is_valid():
            form.save()
            # successful
            messages.success(request, "جزییات محصول تغییر یافت")
            return redirect("vendor:vendor_products")

        # there are form errors
        messages.error(request, "در جریان ثبت تغییرات مشکلی بوجود آمد!")
        return render(request, "vendor/edit_product.html", context=locals())

    # GET
    form = ProductForm(instance=product)
    return render(request, "vendor/edit_product.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def delete_product(request, id):
    """this view enables a vendor to delete a product"""
    product = Product.objects.filter(id=id, vendor=request.user.vendor).first()
    if product:
        product.delete()
        messages.success(request, "محصول موفقانه حذف گردید.")
        return redirect("vendor:vendor_products")
    else:
        messages.error(request, "چنین محصولی وجود ندارد!")
    return redirect("vendor:vendor_products")



