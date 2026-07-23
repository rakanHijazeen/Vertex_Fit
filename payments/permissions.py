from django.core.exceptions import ObjectDoesNotExist
from rest_framework.permissions import BasePermission


class SubscriptionPermissionBase(BasePermission):
    """Shared helpers for subscription-aware permissions."""

    message = "A valid subscription is required for this feature."

    def _get_subscription(self, request):
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return None

        try:
            return user.subscription
        except (AttributeError, ObjectDoesNotExist):
            return None


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
    message = "You have reached your retroactive video upload limit for this billing period."

    def has_permission(self, request, view):
        sub = self._get_subscription(request)
        if not sub:
            self.message = "An active subscription is required to upload retroactive video."
            return False

        if sub.status != "active":
            self.message = "Your subscription is not active."
            return False

        sub.reset_usage_if_needed()

        return sub.can_upload_retroactive_video