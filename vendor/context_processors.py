from vendor.models import Vendor


def vendor_context(request):
    try:
        if request.user != "AnonymousUser":
            vendor = Vendor.objects.get(user=request.user)
            return {"vendor": vendor}
    except:
        return {"vendor": None}
