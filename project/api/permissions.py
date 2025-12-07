from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from order.models import ORDER_STATUS_CHOICES
from rest_framework.permissions import BasePermission
from accounts.models import REST, CUSTOMER


class IsCarrierOfVendor(BasePermission):
    """this handle both order permission and carrier permission"""

    def has_permission(self, request, view):
        """first, is it a carrier and is it active"""
        if not hasattr(request.user, "carrier"):
            raise PermissionDenied(detail="not_allowed")
        return True

    def has_object_permission(self, request, view, order_obj):
        """last, is this carrier allowed to see these items"""
        carrier = request.user.carrier
        return carrier.vendor == order_obj.vendor


class IsOrderPreparingState(BasePermission):
    """prevents any order if not in 'preparing' status to be marked as carrying"""

    def has_object_permission(self, request, view, order_obj):
        if order_obj.status != ORDER_STATUS_CHOICES[2][0]:
            print("order not in preparing state")
            return False
        return True


class IsOrderCarryingState(BasePermission):
    """prevents any order if not in 'waiting' status to be marked as carrying"""

    def has_object_permission(self, request, view, order_obj):
        if order_obj.status != ORDER_STATUS_CHOICES[3][0]:
            print("order not in carrying mode")
            return False
        return True


class IsVendor(BasePermission):

    def has_permission(self, request, view):
        if request.user.role != REST or not hasattr(request.user, "vendor"):
            raise PermissionDenied(detail="user_not_vendor")
        return True


class IsVendorOfObject(BasePermission):
    """
    check whether a user is a vendor or not
    and whether requesting user/vendor owns carrier/order/food
    """

    def has_permission(self, request, view):
        if request.user.role != REST or not hasattr(request.user, "vendor"):
            raise PermissionDenied(detail="user_not_vendor")
        return True

    def has_object_permission(self, request, view, obj):
        if obj.vendor:
            return obj.vendor == request.user.vendor
        return False


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        if request.user.role != CUSTOMER:
            print("user_not_customer")
            raise PermissionDenied(detail="user_not_customer")
        return True


class IsBuyer(BasePermission):
    def has_permission(self, request, view):
        if request.user.role != CUSTOMER:
            raise PermissionDenied(detail="user_not_buyer")
        return True

    def has_object_permission(self, request, view, obj):
        """checks whether the requesting user owns the order"""
        if obj.user:
            return obj.user == request.user
        return False


class IsHavingCart(BasePermission):
    """only customers have cart"""

    def has_permission(self, request, view):
        if not (hasattr(request.user, "cart") and request.user.role == CUSTOMER):
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
        if request.user.role != REST or not request.user.vendor.is_approved:
            raise PermissionDenied(detail="vendor_not_approved")
        return True


class IsProfileOwner(BasePermission):

    def has_object_permission(self, request, view, obj):
        # return True for GET, HEAD and OPTIIONS
        if request.user.profile != obj:
            return False
        return True
