from rest_framework.permissions import BasePermission


class IsProfileOwner(BasePermission):

    def has_object_permission(self, request, view, obj):
        # return True for GET, HEAD and OPTIIONS
        if request.user.profile != obj:
            return False
        return True
