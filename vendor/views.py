from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from accounts.models import UserProfile
from catalog.models import Category, Product
from vendor.forms import CategoryForm, ProductForm, VendorForm
from vendor.models import Vendor
from accounts.forms import UserProfileForm
from django.contrib import messages
from django.utils.text import slugify
from django.urls import reverse

# Create your views here.


# utility funciton
def vendor_tester(user):
    if user.role != 1 or not hasattr(user, "vendor"):
        raise PermissionDenied
    return True


# utility functions
def get_vendor(req):
    return req.user.vendor


@login_required
@user_passes_test(vendor_tester)
def vendor_profile(request):
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
            messages.success(request, "Your profile has been updated.")
            return redirect("vendor:vendor_profile_edit")
        # there were errros
        return render(
            request,
            "vendor/profile.html",
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
                "vendor/profile.html",
                {
                    "vendor_form": vendor_form,
                    "profile_form": vendor_user_profile_form,
                    "profile": vendor_user_profile,
                },
            )
        return HttpResponse("You are not a vendor")


@login_required
@user_passes_test(vendor_tester)
def vend_dashboard(request):
    vendor = Vendor.objects.get(user=request.user)
    return render(request, "vendor/vend_dashboard.html", {"vendor": vendor})


@login_required
@user_passes_test(vendor_tester)
def catalog_builder(request):
    # sending all related products of this vendor
    categories = Category.objects.filter(vendor=request.user.vendor)
    return render(request, "vendor/catalog_builder.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def products_by_category(request, cat_id):
    category = Category.objects.get(id=cat_id)
    products = Product.objects.filter(vendor=get_vendor(request), category_id=cat_id)
    return render(request, "vendor/products_by_category.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def add_category(request):
    # POST
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.vendor = request.user.vendor
            category.slug = slugify(form.cleaned_data["name"])
            category.save()
            # successfull
            messages.success(request, "Category Added Successfully")
            return redirect("vendor:catalog_builder")
        # there are form errors
        messages.error(request, "An error occured during saving the category!")
        return render(request, "vendor/add_category.html", context=locals())
    # GET
    form = CategoryForm()
    return render(request, "vendor/add_category.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def edit_category(request, id):
    category = Category.objects.filter(id=id).first()
    if not category:
        # redirect the user back to catalog builder if no category
        return redirect("vendor:catalog_builder")
    # POST
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save(commit=False)
            category.slug = slugify(form.cleaned_data["name"])
            category.save()
            # successfull
            messages.success(request, "Category Updated Successfully")
            return redirect("vendor:catalog_builder")
        # there are form errors
        messages.error(request, "An error occured during saving the changes!")
        return render(request, "vendor/edit_category.html", context=locals())
    # GET
    form = CategoryForm(instance=category)
    return render(request, "vendor/edit_category.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def delete_category(request, id):
    category = Category.objects.filter(id=id).first()
    if category:
        # redirect the user back to catalog builder if no category
        category.delete()
        messages.success(request, "Category deleted successfully!")
    else:
        messages.error(request, "There is no such category")
    return redirect("vendor:catalog_builder")


@login_required
@user_passes_test(vendor_tester)
def add_product(request):
    # POST
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor = request.user.vendor
            product.save()
            # successfull
            messages.success(request, "محصول موفقانه ثبت شد")
            return redirect("vendor:catalog_builder")
        # there are form errors
        messages.error(request, "خطا در ثبت محصول!")
        return render(request, "vendor/add_product.html", context=locals())
    # GET
    form = ProductForm()
    return render(request, "vendor/add_product.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def edit_product(request, id):
    product = Product.objects.filter(id=id).first()
    if not product:
        # redirect the user back to catalog builder if no category
        return redirect("vendor:catalog_builder")
    # POST
    if request.method == "POST":
        category_id = product.category.id

        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            # successful
            messages.success(request, "جزییات محصول تغییر یافت")
            return redirect(
                reverse("vendor:products_by_category", kwargs={"cat_id": category_id})
            )

        # there are form errors
        messages.error(request, "در جریان ثبت تغییرات مشکلی بوجود آمد!")
        return redirect(reverse("vendor:products_by_category", args=[category_id]))

    # GET
    form = ProductForm(instance=product)
    return render(request, "vendor/edit_product.html", context=locals())


@login_required
@user_passes_test(vendor_tester)
def delete_product(request, id):
    product = Product.objects.filter(id=id).first()
    if product:
        # redirect the user back to catalog builder if no category
        category_id = product.category.id
        product.delete()
        messages.success(request, "محصول موفقانه حذف گردید.")
        return redirect(reverse("vendor:products_by_category", args=[category_id]))
    else:
        messages.error(request, "چنین محصولی وجود ندارد!")
    return redirect("vendor:catalog_builder")
