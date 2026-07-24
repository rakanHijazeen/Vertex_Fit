from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission

from .models import PlanTier
from .usage import get_user_subscription


class SubscriptionPermissionBase(BasePermission):
    """Shared helpers for subscription-aware permissions."""

    message = "A valid subscription is required for this feature."

    def _get_subscription(self, request):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        return get_user_subscription(user)


class IsProUser(SubscriptionPermissionBase):
    message = "This feature requires an active Pro or VIP subscription."

    def has_permission(self, request, view):
        sub = self._get_subscription(request)
        if not sub:
            return False

        return sub.status == "active" and sub.tier in {"pro", "vip"}


class IsVIPUser(SubscriptionPermissionBase):
    message = "This feature requires an active VIP subscription."

    def has_permission(self, request, view):
        sub = self._get_subscription(request)
        if not sub:
            return False

        return sub.status == "active" and sub.tier == "vip"


class HasLiveCoachTime(SubscriptionPermissionBase):
    message = "You have exhausted your live coach time for this billing period."

    def has_permission(self, request, view):
        sub = self._get_subscription(request)
        if not sub:
            self.message = "An active subscription is required to use live coach time."
            return False

        if sub.status != "active":
            self.message = "Your subscription is not active."
            return False

        sub.reset_usage_if_needed()

        if sub.can_use_live_coach:
            return True

        self.message = (
            "You have exhausted your live coach time for this billing period. "
            "Please wait for the next reset or upgrade your plan."
        )
        return False


class CanUploadRetroactiveVideo(SubscriptionPermissionBase):
    message = "You have reached your retroactive video upload limit."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return False

        sub = self._get_subscription(request)

        # Free users are handled by the view-level quota check.
        if not sub or sub.tier == PlanTier.FREE.value:
            return True

        # For paid subscribers, trigger usage resets & check their tier allowance.
        if sub.status != "active":
            self.message = "Your subscription is not active."
            return False

        sub.reset_usage_if_needed()
        return sub.can_upload_retroactive_video