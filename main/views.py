from django.shortcuts import render
from django.contrib import messages

from vendor.models import Vendor
# Create your views here.

def home(request):
    vendors = Vendor.objects.filter(is_approved=True,user__is_active=True)
    return render(request,"base/home.html",context=locals())