from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsVendorOfFood(BasePermission):
    
    def has_object_permission(self, request, view, obj):
        # return True for GET, HEAD and OPTIIONS
        if request.method in SAFE_METHODS:
            return True
        if not hasattr(request.user,"vendor"):
            return False
        return obj.vendor == request.user.vendor
    

class IsHavingCart(BasePermission):
    """only customers have cart"""
    def has_permission(self, request, view):
        if not hasattr(request.user,"cart"):
            return False
        return True