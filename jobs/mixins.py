from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class OwnerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Ensures the user is logged in and has the owner role.
    """

    def test_func(self):
        user = self.request.user
        return bool(
            user.is_authenticated
            and (
                getattr(user, "is_superuser", False)
                or (hasattr(user, "profile") and user.profile.is_owner)
            )
        )

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("You do not have permission to access the owner portal.")


class TechnicianRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Ensures the user is logged in and has the technician role.
    """

    def test_func(self):
        user = self.request.user
        return bool(
            user.is_authenticated
            and hasattr(user, "profile")
            and user.profile.is_technician
        )

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        raise PermissionDenied("You do not have permission to access the technician portal.")
