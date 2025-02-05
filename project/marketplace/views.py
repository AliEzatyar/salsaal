from django.shortcuts import render
from django.core.paginator import Paginator
from vendor.models import Vendor

# Create your views here.


def vendors(request,page=None, category_slug=None, rating=None, city=None):
    vendors = Vendor.objects.filter(is_approved=True)
    if category_slug:
        vendors.filter(category__slug=category_slug)
    if city:
        vendors.filter(user_profile__city=city)
    vendors.select_related("user_profile")
    paginated = Paginator(vendors,per_page=6)
    amount_pages = [i for i in range(1,paginated.num_pages+1)]
    # default is the first page
    vendors = paginated.get_page(1)
    # case sepecific page requested
    if page:
        try:
            page = int(page)
            vendors = paginated.get_page(page)
        except:
            pass
    
    return render(request, "marketplace/vendors_list.html", context=locals())
