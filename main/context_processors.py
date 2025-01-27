from vendor.models import Vendor
from catalog.models import Category

def categories_context(request):
    return {"categories":Category.objects.all()}