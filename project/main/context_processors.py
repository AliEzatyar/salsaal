from vendor.models import Vendor
from marketplace.models import Category

def categories_context(request):
    context = {"categories": Category.objects.values("name","slug")}
    # handling cart and fav list badges
    if request.user.is_authenticated and hasattr(request.user, "cart") and hasattr(request.user,"favlist"):
        """if the user has a cart associated with it, return total cart items"""
        context["cart_badge"] = request.user.cart.calculate_total_items()
        context["favlist_badge"] = request.user.favlist.total_items()
    else:
        context["cart_badge"] = 0
        context["favlist_badge"] = 0

    return context
