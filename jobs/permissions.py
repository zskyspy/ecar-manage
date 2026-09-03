from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """
    Allows access only to authenticated users with the 'owner' role.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "profile")
            and request.user.profile.is_owner
        )


class IsTechnician(BasePermission):
    """
    Allows access only to authenticated users with the 'technician' role.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "profile")
            and request.user.profile.is_technician
        )


class IsAssignedTechnician(BasePermission):
    """
    Allows access only if the authenticated user is the assigned technician of the job.
    """

    def has_object_permission(self, request, view, obj):
        return bool(
            request.user
            and request.user.is_authenticated
            and obj.assigned_technician == request.user
        )

