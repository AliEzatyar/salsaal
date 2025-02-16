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


def marketplace(request, query=None):
    """this view presents markeplace page. It also hanldes search, sort and filtering products"""
    products = Product.objects.filter(is_available=True)
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
    # handling search
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
