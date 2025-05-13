from rest_framework.permissions import BasePermission
from accounts.models import SHOP, CUSTOMER, CARRIER


class IsCarrierOfVendor(BasePermission):
    """this handle both order permission and carrier permission"""

    def has_permission(self, request, view):
        """first, is it a carrier?"""
        if not hasattr(request.user, "carrier"):
            print("fist false")
            
            return False
        if not request.user.carrier.is_active:
            """only active carriers can see available orders"""
            print("is not active", request.user.role)
            return False
        return True

    def has_object_permission(self, request, view, order_obj):
        """last, is this carrier allowed to see these items?"""
        carrier = request.user.carrier
        return carrier.vendor == order_obj.vendor and carrier.is_active == True


class IsVendor(BasePermission):
    def has_permission(self, request, view):
        if not hasattr(request.user, "vendor") or request.user.role != SHOP:
            return False
        return True


class IsVendorOfOrder(BasePermission):
    def has_permission(self, request, view):
        if not hasattr(request.user, "vendor") or request.user.role != SHOP:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        return obj.vendor == request.user.vendor


class IsVendorOfCarrier(BasePermission):

    def has_object_permission(self, request, view, obj):
        if not request.user.role == SHOP:
            return False
        return request.user.vendor == obj.vendor


class IsBuyer(BasePermission):
    def has_permission(self, request, view):
        if request.user.role != CUSTOMER:
            return False
        return True

    def has_object_permission(self, request, view, obj):
        """checks whether the requesting user owns the order"""
        return obj.user == request.user
