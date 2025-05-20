from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied


from rest_framework.permissions import BasePermission
from accounts.models import REST, CUSTOMER


class IsCarrierOfVendor(BasePermission):
    """this handle both order permission and carrier permission"""

    def has_permission(self, request, view):
        """first, is it a carrier"""
        if not hasattr(request.user, "carrier"):
            raise PermissionDenied(detail="user_not_carrier")
        if not request.user.carrier.is_active:
            """only active carriers can see available orders"""
            raise PermissionDenied(detail="carrier_disabled")
        return True

    def has_object_permission(self, request, view, order_obj):
        """last, is this carrier allowed to see these items"""
        carrier = request.user.carrier
        return carrier.vendor == order_obj.vendor and carrier.is_active == True


class IsVendor(BasePermission):
    """check whether a user is a vendor or not"""

    def has_permission(self, request, view):
        if not hasattr(request.user, "vendor") or request.user.role != REST:
            raise PermissionDenied(detail="user_not_vendor")
        return True


class IsVendorOfOrder(BasePermission):
    def has_permission(self, request, view):
        if not hasattr(request.user, "vendor") or request.user.role != REST:
            raise PermissionDenied(detail="user_not_vendor")
        return True

    def has_object_permission(self, request, view, obj):
        return obj.vendor == request.user.vendor


class IsVendorOfCarrier(BasePermission):

    def has_object_permission(self, request, view, obj):
        if not request.user.role == REST:
            return False
        return request.user.vendor == obj.vendor


class IsBuyer(BasePermission):
    def has_permission(self, request, view):
        if request.user.role != CUSTOMER:
            raise PermissionDenied(detail="user_not_buyer")
        return True

    def has_object_permission(self, request, view, obj):
        """checks whether the requesting user owns the order"""
        return obj.user == request.user


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
        if not hasattr(request.user, "cart") or request.user.role != CUSTOMER:
            raise PermissionDenied(detail="user_has_no_cart")
        return True


class IsHavingFavlist(BasePermission):
    """only customers have cart"""

    def has_permission(self, request, view):
        if not hasattr(request.user, "favlist") or request.user.role != CUSTOMER:
            raise PermissionDenied(detail="user_has_no_favlist")
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
