from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied

from vendor.models import Vendor

# Create your views here.


# utility funciton
def vendor_tester(user):
    if user.role != 1:
        raise PermissionDenied
    return True


@login_required
@user_passes_test(vendor_tester)
def vendor_profile(request):
    vendor = Vendor.objects.get(user=request.user)
    return render(request, "vendor/profile.html", {"vendor": vendor})


@login_required
@user_passes_test(vendor_tester)
def vend_dashboard(request):
    vendor = Vendor.objects.get(user=request.user)
    return render(request, "vendor/vend_dashboard.html", {"vendor": vendor})
