from django.shortcuts import redirect, render
from django.core.paginator import Paginator
from marketplace.models import Category, Product
from vendor.models import Vendor


# Create your views here.
def product_detail(request, product_id):
    product = Product.objects.filter(id=product_id).first()
    if product:
        return render(request, "marketplace/product_detail.html", context=locals())
    return redirect("main:home")


def vendors(request, page=None):
    """this view presents all available vendors by either category, city or rating"""
    vendors = Vendor.objects.filter(is_approved=True)
    if "query" in request.GET:
        vendors = vendors.filter(vendor_name__icontains=request.GET["query"])
        amount_vendors = vendors.count()  # number of vendors found after all filterings

        return render(request, "marketplace/vendors_list.html", context=locals())

    cities = {vendor.user_profile.city for vendor in vendors}  # needed in template
    params = {}
    for key, value in request.GET.items():
        """this loop adds or updates url parameters comming in get request"""
        if value:
            if key == "category_slug":
                # we have to customize category --> filter(categories__in=[id]).distinct()
                value = [Category.objects.filter(slug=value).first().id]
                key = "categories__in"
            params[key] = value
    # applying all filters according to parameters
    vendors = vendors.filter(**params).distinct()
    vendors = vendors.select_related("user_profile", "user")  # for time optimizing
    amount_vendors = vendors.count()  # number of vendors found after all filterings

    # paginating the results
    paginated = Paginator(vendors, per_page=6)
    page_numbers = [i for i in range(1, paginated.num_pages + 1)]

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
