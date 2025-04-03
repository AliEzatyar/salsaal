from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsVendorOfProduct(BasePermission):
    
    def has_object_permission(self, request, view, obj):
        # return True for GET, HEAD and OPTIIONS
        if request.method in SAFE_METHODS:
            return True
        if not hasattr(request.user,"vendor"):
            return False
        return obj.vendor == request.user.vendor