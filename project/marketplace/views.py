import json
from django.http.response import JsonResponse
from django.shortcuts import redirect, render
from django.core.paginator import Paginator
from marketplace.models import Category, Food, Rating
from main.utils import query_execution_time
from accounts.utils import user_test
from django.db.models.aggregates import Count
from django.core.paginator import Paginator
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import RatingForm
from django.contrib.contenttypes.models import ContentType
from .serializers import FoodSerializer
from rest_framework import filters
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response
from api.backends import FoodFilterSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, views
from vendor.models import Vendor
from vendor.serializers import VendorSerializer
from marketplace.serializers import FoodSerializer, RatingSerializer
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D


"""Marketplace API Views"""


class FoodReadViewSet(viewsets.ReadOnlyModelViewSet):
    """this view only handles representation of foods to normal users"""

    queryset = Food.objects.filter(is_available=True)
    serializer_class = FoodSerializer
    permission_classes = [permissions.AllowAny]
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["name", "price"]
    ordering = ["price"]
    # filering
    filterset_class = FoodFilterSet
    # searching
    search_fields = ["name", "category__name", "description", "vendor__vendor_name"]


class RatingViewSet(viewsets.ModelViewSet):
    queryset = Rating.objects.filter(enabled=True)
    serializer_class = RatingSerializer
    # ordering
    filter_backends = [
        filters.OrderingFilter,
        filters.SearchFilter,
        DjangoFilterBackend,
    ]
    ordering_fields = ["created_at", "rating"]
    ordering = ["created_at"]

    def get_queryset(self):
        """overriding in order to distinguish by vendor or food"""
        object_id = self.request.query_params.get("obj_id", None)
        query_set = self.queryset
        if object_id:
            query_set = self.queryset.filter(object_id=int(object_id))
        return query_set

    def create(self, request, *args, **kwargs):
        rating_type = request.query_params.get("type")
        obj_id = request.query_params.get("obj_id")
        if not rating_type or not obj_id:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        data = request.data
        previous = Rating.objects.filter(
            object_id=int(obj_id), user=request.user
        ).first()
        # handling indirect update
        if previous:
            # prviously exists, performing update
            previous.comment = data["comment"]
            previous.rating = data["rating"]
            previous.enabled = True
            previous.save()
            return Response({"updated": True}, status=status.HTTP_200_OK)

        else:
            # performing new rating creation
            serializer = self.get_serializer(data=data)
            try:
                serializer.is_valid(raise_exception=True)
            except:
                return Response(
                    {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
                )
            self.perform_create(
                serializer
            )  # sets instance to serializer after creation
            instance = serializer.instance
            if rating_type == "vendor":
                instance.content_type = ContentType.objects.get_for_model(Vendor)
            elif rating_type == "food":
                instance.content_type = ContentType.objects.get_for_model(Food)
            instance.object_id = int(obj_id)
            instance.enabled = True
            instance.save()
            # successfull creation
            return Response(serializer.data, status=status.HTTP_201_CREATED)


"""Advanced search"""


class SearchApiView(views.APIView):
    """This api view handles searching for both food and vendor objects considering distance"""

    def get(self, *args, **kwargs):
        query = self.request.query_params.get("query", None)
        log = self.request.query_params.get("long", None)
        lat = self.request.query_params.get("lat", None)
        max_distance = self.request.query_params.get("max_distance", 5)

        # determinig user location
        try:
            if lat and log:
                user_location = Point(float(log), float(lat), srid=4326)
            else:
                user_location = self.request.user.profile.location
        except:
            Response(
                {"error": "invalid location data"}, status=status.HTTP_400_BAD_REQUEST
            )

        # handling empty query
        if not query or not query.strip():
            return Response(
                {"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # search for foods
        foods = Food.objects.filter(
            name__icontains=query, is_available=True
        ).select_related("vendor__user_profile")

        foods = foods.annotate(
            distance=Distance("vendor__user_profile__location", user_location)
        )
        # limiting distance
        foods = foods.filter(distance__lte=D(km=max_distance))
        foods_serializer = FoodSerializer(foods, many=True)

        # vendors found by query and limiting distance
        vendors = (
            Vendor.objects.filter(
                vendor_name__icontains=query, is_approved=True, user__is_active=True
            )
            .annotate(distance=Distance("user_profile__location", user_location))
            .filter(distance__lte=D(km=max_distance))
        )
        # preparing as json
        vendors_serializer = VendorSerializer(vendors, many=True)
        total_found = len(vendors) + len(foods)
        # success
        return Response(
            {
                "total": total_found,
                "foods": foods_serializer.data,
                "vendors": vendors_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


def marketplace(request):
    """this view presents markeplace page. It also hanldes search, sort and filter of foods"""
    all_foods = Food.objects.filter(is_available=True)
    foods = all_foods

    # filter by category
    if request.method == "GET" and "category" in request.GET:
        foods = foods.filter(category__name=request.GET["category"])
    
    categories_by_foods_count = Category.objects.annotate(
        foods_count=Count("foods")
    )
    paginated = Paginator(foods, 6)
    if request.method == "POST":
        """handling filter, sort and search"""
        # search handling
        if "query" in request.POST:
            foods = foods.filter(name__icontains=request.POST["query"])
            
            paginated = Paginator(foods, 6)
            total_pages = [i + 1 for i in range(paginated.num_pages)]
            total_found = foods.count()
            # first page by default
            foods = paginated.get_page(1)
            return render(request, "marketplace/marketplace.html", context=locals())

        # the option attribute contains all filtering and sorting
        data = json.loads(request.body)["options"]

        # filtering
        if "category" in data:
            foods = foods.filter(category__id=int(data["category"]))
        if "price" in data:
            foods = foods.filter(
                price__range=[int(data["price"][0]), int(data["price"][1])]
            )
        if "rating" in data:
            foods = foods.filter(id__in=[p.id for p in foods if round(p.overall_rating())==int(data['rating'])])    
        
        # sorting
        if "sort" in data:
            sort_type = data["sort"]
            if sort_type == "newest":
                foods = foods.order_by("-created_at")
            elif sort_type == "cheapest":
                foods = foods.order_by("price")
            elif sort_type == "costly":
                foods = foods.order_by("-price")

        # paginating the results finally
        paginated = Paginator(foods, 6)
        total_pages = paginated.num_pages
        total_found = foods.count()

        # first page by default
        foods = paginated.get_page(1)
        if "page" in data:
            foods = paginated.get_page(int(data["page"]))
        str_html = render_to_string(
            "marketplace/portional_list.html",
            {"foods": foods},
        )
        return JsonResponse(
            {"html": str_html, "total_pages": total_pages, "total_found": total_found}
        )

    # initial marketplace page
    total_found = foods.count()
    total_pages = [i + 1 for i in range(paginated.num_pages)]
    foods = paginated.get_page(1)
    one_star_count = len(
        [p.overall_rating for p in all_foods if round(p.overall_rating()) == 1]
    )
    two_star_count = len(
        [p.overall_rating for p in all_foods if round(p.overall_rating()) == 2]
    )
    three_star_count = len(
        [p.overall_rating for p in all_foods if round(p.overall_rating()) == 3]
    )
    four_star_count = len(
        [p.overall_rating for p in all_foods if round(p.overall_rating()) == 4]
    )
    five_star_count = len(
        [p.overall_rating for p in all_foods if round(p.overall_rating()) == 5]
    )

    return render(request, "marketplace/marketplace.html", context=locals())


def food_detail(request, food_id):
    food = Food.objects.filter(id=food_id).first()
    ratings = Rating.objects.filter(object_id=food.id).select_related("user")
    if food:
        return render(request, "marketplace/food_detail.html", context=locals())
    return redirect("main:home")


@query_execution_time
def vendors(request, page=None):
    """this view presents all available vendors by either category, city or rating"""
    all_vendors = Vendor.objects.filter(is_approved=True)
    vendors = all_vendors
    paginated = Paginator(vendors, per_page=6)
    if request.method == "POST":
        # handling search NOT AJAX
        if "query" in request.POST:
            vendors = vendors.filter(vendor_name__icontains=request.POST["query"])
            cities = {
                vendor.user_profile.city for vendor in vendors
            }  # needed in template
            paginated = Paginator(vendors, per_page=6)
            total_found = vendors.count()
            total_pages = [i + 1 for i in range(paginated.num_pages)]
            vendors = paginated.get_page(1)
            return render(request, "marketplace/vendors_list.html", context=locals())

        data = json.loads(request.body)["options"]
        # filtering
        if "city" in data:
            vendors = vendors.filter(user_profile__city=data["city"])
        if "category" in data:
            vendors = vendors.filter(categories__in=[int(data["category"])]).distinct()
        if "rating" in data:
            vendors = vendors.filter(id__in=[v.id for v in vendors if round(v.overall_rating())==int(data['rating'])])    
        
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
                page = int(data["page"])
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
    # rating counts
    one_star_count = len(
        [p.overall_rating for p in all_vendors if int(p.overall_rating()) == 1]
    )
    two_star_count = len(
        [p.overall_rating for p in all_vendors if int(p.overall_rating()) == 2]
    )
    three_star_count = len(
        [p.overall_rating for p in all_vendors if int(p.overall_rating()) == 3]
    )
    four_star_count = len(
        [p.overall_rating for p in all_vendors if int(p.overall_rating()) == 4]
    )
    five_star_count = len(
        [p.overall_rating for p in all_vendors if int(p.overall_rating()) == 5]
    )

    return render(request, "marketplace/vendors_list.html", context=locals())


@login_required
@user_passes_test(user_test)
def rate(request):
    """this view handles rating a food or a vendor"""
    data = json.loads(request.body)["options"]
    form = RatingForm(data)
    type_ = data["type"]
    previous = Rating.objects.filter(
        object_id=int(data["object_id"]), user=request.user
    ).first()
    # handling indirect update
    if previous:
        # prviously exists, performing update
        previous.comment = data['comment']
        previous.rating = data['rating']
        previous.save()
        return JsonResponse({"OK": True})

    if form.is_valid():
        rating = form.save(commit=False)
        if type_ == "food":
            rating.content_type = ContentType.objects.get_for_model(Food)
        elif type_ == "vendor":
            rating.content_type = ContentType.objects.get_for_model(Vendor)
        rating.object_id = data["object_id"]
        rating.user = request.user
        rating.save()
        return JsonResponse({"OK": True})
