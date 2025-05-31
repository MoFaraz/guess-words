from rest_framework.permissions import BasePermission

class IsGameAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and getattr(request.user, 'role', None) == 'admin')


class IsAdminOrCreatorWhileWaiting(BasePermission):

    def has_object_permission(self, request, view, obj):
        if request.user and request.user.role == 'admin' and obj.status == 1:
            return True

        return obj.creator == request.user and obj.status == 1