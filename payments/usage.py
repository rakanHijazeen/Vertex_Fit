from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F

from .models import UserSubscription


def get_user_subscription(user):
    """Return the user's subscription if it exists, otherwise None."""
    if not user or not getattr(user, "is_authenticated", False):
        return None

    try:
        return user.subscription
    except (AttributeError, ObjectDoesNotExist):
        return None


def check_retroactive_upload_quota(user):
    """Reset usage if needed and return the subscription plus any quota error."""
    subscription = get_user_subscription(user)
    if not subscription:
        return None, "An active subscription is required to upload retroactive video."

    subscription.reset_usage_if_needed()

    if subscription.status != "active":
        return None, "Your subscription is not active."

    if not subscription.can_upload_retroactive_video:
        return None, "You have reached your retroactive video upload limit for this billing period."

    return subscription, None


def consume_retroactive_upload_usage(user):
    """Atomically increment the retroactive upload counter after processing completes."""
    subscription = get_user_subscription(user)
    if not subscription:
        return False, "An active subscription is required to upload retroactive video."

    with transaction.atomic():
        locked_subscription = UserSubscription.objects.select_for_update().get(pk=subscription.pk)
        locked_subscription.reset_usage_if_needed()

        if locked_subscription.status != "active":
            return False, "Your subscription is not active."

        if not locked_subscription.can_upload_retroactive_video:
            return False, "You have reached your retroactive video upload limit for this billing period."

        locked_subscription.retroactive_uploads_count = F("retroactive_uploads_count") + 1
        locked_subscription.save(update_fields=["retroactive_uploads_count"])

    return True, None


def check_live_coach_quota(user):
    """Reset usage if needed and verify live coach time remains."""
    subscription = get_user_subscription(user)
    if not subscription:
        return None, "An active subscription is required to use live coach time."

    subscription.reset_usage_if_needed()

    if subscription.status != "active":
        return None, "Your subscription is not active."

    if not subscription.can_use_live_coach:
        return None, "You have exhausted your live coach time for this billing period."

    return subscription, None


def consume_live_coach_seconds(user, seconds_used):
    """Atomically increment live coach seconds after a coaching exchange completes."""
    subscription = get_user_subscription(user)
    if not subscription:
        return False, "An active subscription is required to use live coach time."

    if seconds_used <= 0:
        return True, None

    with transaction.atomic():
        locked_subscription = UserSubscription.objects.select_for_update().get(pk=subscription.pk)
        locked_subscription.reset_usage_if_needed()

        if locked_subscription.status != "active":
            return False, "Your subscription is not active."

        max_seconds = locked_subscription.live_coach_minute_limit * 60
        remaining_seconds = max_seconds - locked_subscription.live_coach_seconds_used
        if remaining_seconds < seconds_used:
            return False, "You have exhausted your live coach time for this billing period."

        locked_subscription.live_coach_seconds_used = F("live_coach_seconds_used") + seconds_used
        locked_subscription.save(update_fields=["live_coach_seconds_used"])

    return True, None