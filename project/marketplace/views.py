import json
from django.http.response import JsonResponse
from django.shortcuts import redirect, render
from django.core.paginator import Paginator
from marketplace.models import Category, Product
from main.utils import query_execution_time
from vendor.models import Vendor
from django.db.models.aggregates import Count
from django.core.paginator import Paginator
from django.template.loader import render_to_string

    
def marketplace(request):
    """this view presents markeplace page. It also hanldes search, sort and filtering products"""
    products = Product.objects.filter(is_available=True)
    
    if request.method == "GET" and 'category' in request.GET:
        products = products.filter(category__slug=request.GET['category'])
    categories_by_products_count = Category.objects.annotate(
        products_count=Count("products")
    )
    paginated = Paginator(products, 6)
    if request.method == "POST":
        """handling filter, sort and search"""
        # search handling
        if "query" in request.POST:
            products = products.filter(name__icontains=request.POST['query'])
            paginated = Paginator(products, 6)
            total_pages = [i + 1 for i in range(paginated.num_pages)]
            total_found = products.count()
            # first page by default
            products = paginated.get_page(1)
            return render(request, "marketplace/marketplace.html", context=locals())

        # the option attribute contains all filtering and sorting
        data = json.loads(request.body)["options"]

        # filtering
        if "category" in data:
            products = products.filter(category__id=int(data["category"]))
        if "price" in data:
            products = products.filter(
                price__range=[int(data["price"][0]), int(data["price"][1])]
            )
        # sorting
        if "sort" in data:
            sort_type = data["sort"]
            if sort_type == "newest":
                products = products.order_by("-created_at")
            elif sort_type == "cheapest":
                products = products.order_by("price")
            elif sort_type == "costly":
                products = products.order_by("-price")

        # paginating the results finally
        paginated = Paginator(products, 6)
        total_pages = paginated.num_pages
        total_found = products.count()

        # first page by default
        products = paginated.get_page(1)
        if "page" in data:
            products = paginated.get_page(int(data["page"]))
        str_html = render_to_string(
            "marketplace/portional_list.html",
            {"products": products},
        )
        return JsonResponse(
            {"html": str_html, "total_pages": total_pages, "total_found": total_found}
        )

    # initial marketplace page
    total_found = products.count()
    total_pages = [i + 1 for i in range(paginated.num_pages)]
    products = paginated.get_page(1)
    return render(request, "marketplace/marketplace.html", context=locals())


def product_detail(request, product_id):
    product = Product.objects.filter(id=product_id).first()
    if product:
        return render(request, "marketplace/product_detail.html", context=locals())
    return redirect("main:home")


@query_execution_time
def vendors(request, page=None):
    """this view presents all available vendors by either category, city or rating"""
    vendors = Vendor.objects.filter(is_approved=True)
    paginated = Paginator(vendors, per_page=6)
    if request.method == "POST":
        # handling search NOT AJAX
        if "query" in request.POST:
            vendors = vendors.filter(vendor_name__icontains=request.POST['query'])
            cities = {vendor.user_profile.city for vendor in vendors}  # needed in template
            paginated = Paginator(vendors, per_page=6)
            total_found = vendors.count()
            total_pages = [i + 1 for i in range(paginated.num_pages)]
            vendors = paginated.get_page(1)
            return render(request, "marketplace/vendors_list.html", context=locals())

        data = json.loads(request.body)["options"]
        # filtering
        if "city" in data:
            vendors = vendors.filter(user_profile__city=data['city'])
        if "category" in data:
            vendors = vendors.filter(categories__in=[int(data['category'])]).distinct()

        # applying all filters according to parameters
        vendors = vendors.select_related("user_profile", "user")  # for time optimizing
        total_found = vendors.count()  # number of vendors found after all filterings

        # paginating the results
        paginated = Paginator(vendors, per_page=6)
        total_pages = [i for i in range(1, paginated.num_pages + 1)]
        cities = {vendor.user_profile.city for vendor in vendors}  # needed in template

        # default is the first page
        vendors = paginated.get_page(1)
        # case sepecific page requested
        if "page" in data:
            try:
                page = int(data['page'])
                vendors = paginated.get_page(page)
            except:
                pass
        str_html = render_to_string(
            "marketplace/vendors_portional_list.html", context=locals()
        )
        return JsonResponse(
            {"html": str_html, "total_pages": total_pages, "total_found": total_found}
        )
    # GET

    cities = {vendor.user_profile.city for vendor in vendors}  # needed in template
    paginated = Paginator(vendors, per_page=6)
    total_found = vendors.count()
    total_pages = [i + 1 for i in range(paginated.num_pages)]
    vendors = paginated.get_page(1)
    return render(request, "marketplace/vendors_list.html", context=locals())
