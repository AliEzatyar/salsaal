from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsCarrierOfVendor(BasePermission):
    """this handle both order permission and carrier permission"""

    def has_permission(self, request, view):
        """first, is it a carrier?"""
        if not hasattr(request.user, "carrier"):
            return False
        return True

    def has_object_permission(self, request, view, order_obj):
        """last, is this carrier allowed to see these items?"""
        carrier = request.user.carrier
        return carrier.vendor == order_obj.vendor


class IsVendor(BasePermission):
    def has_permission(self, request, view):
        if not hasattr(request.user, "vendor"):
            return False
        return True
