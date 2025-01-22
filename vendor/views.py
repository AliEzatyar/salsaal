from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from accounts.models import UserProfile
from vendor.forms import VendorForm
from vendor.models import Vendor
from accounts.forms import UserProfileForm
from django.contrib import messages

# Create your views here.


# utility funciton
def vendor_tester(user):
    if user.role != 1 or not hasattr(user, "vendor"):
        raise PermissionDenied
    return True


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
            messages.success(request,"Your profile has been updated.")
            return redirect("vendor:vendor_profile_edit")
        # there were errros
        return render(
            request,
            "vendor/profile.html",
            {
                "vendor_form": vendor_form,
                "profile_form": vendor_user_profile_form,
                "vendor": vendor,
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
                    "vendor": vendor,
                    "profile": vendor_user_profile,
                },
            )
        return HttpResponse("You are not a vendor")


@login_required
@user_passes_test(vendor_tester)
def vend_dashboard(request):
    vendor = Vendor.objects.get(user=request.user)
    return render(request, "vendor/vend_dashboard.html", {"vendor": vendor})
