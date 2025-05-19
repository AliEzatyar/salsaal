from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

class IsVendorOfFood(BasePermission):

    def has_permission(self, request, view):
        if not hasattr(request.user, "vendor"):
            raise PermissionDenied(detail="user_not_vendor")
        return True

    def has_object_permission(self, request, view, obj):
        # return True for GET, HEAD and OPTIIONS

        return obj.vendor == request.user.vendor


class IsHavingCart(BasePermission):
    """only customers have cart"""

    def has_permission(self, request, view):
        if not hasattr(request.user, "cart"):
            raise PermissionDenied(detail="user_has_no_cart")
        return True


class NotAdmin(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return True
        if request.user.is_superadmin or request.user.is_admin:
            raise PermissionDenied(detail="admin_not_allowed")
        return True

class IsVendorApproved(BasePermission):
    def has_permission(self, request, view):
        if not hasattr(request.user, "vendor") or not request.user.vendor.is_approved:
            raise PermissionDenied(detail="vendor_not_approved")
        return True

