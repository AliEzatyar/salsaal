from vendor.models import Vendor
from catalog.models import Category

def categories_context(request):
    context = {"categories":Category.objects.all()}
    if request.user.is_authenticated():
        context["cart_badge"] = request.user.cart.calculate_total_items()
        
    return context
