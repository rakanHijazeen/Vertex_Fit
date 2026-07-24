from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F

from workouts.models import WorkoutSession

from .models import PlanTier, UserSubscription


def get_user_subscription(user):
    """Return the user's subscription, creating a default free record if needed."""
    if not user or not getattr(user, "is_authenticated", False):
        return None

    try:
        return user.subscription
    except (AttributeError, ObjectDoesNotExist):
        subscription, _ = UserSubscription.objects.get_or_create(user=user)
        return subscription

FREE_UPLOAD_LIMIT = 3


def _has_paid_retroactive_upload_access(subscription):
    return bool(
        subscription
        and subscription.status == "active"
        and subscription.tier in {PlanTier.PRO.value, PlanTier.VIP.value}
    )

def check_retroactive_upload_quota(user):
    """
    Checks if the user is allowed to upload a video without modifying state.
    """
    subscription = get_user_subscription(user)
    has_paid_access = _has_paid_retroactive_upload_access(subscription)

    # 1. Active paid subscription
    if has_paid_access and subscription is not None:
        subscription.reset_usage_if_needed()
        if not subscription.can_upload_retroactive_video:
            return False, "You have reached your retroactive video upload limit for this billing period."
        return True, None

    # 2. Free tier check (users without a paid active subscription)
    uploaded_count = WorkoutSession.objects.filter(user=user).count()
    if uploaded_count >= FREE_UPLOAD_LIMIT:
        return False, f"You have used all {FREE_UPLOAD_LIMIT} free video uploads. Upgrade to Pro for unlimited uploads!"

    return True, None


def consume_retroactive_upload_usage(user):
    """Atomically increment the retroactive upload counter after processing completes."""
    subscription = get_user_subscription(user)
    has_paid_access = _has_paid_retroactive_upload_access(subscription)

    # Free Tier Branch
    if not has_paid_access or subscription is None:
        uploaded_count = WorkoutSession.objects.filter(user=user).count()
        if uploaded_count > FREE_UPLOAD_LIMIT:
            return False, f"You have reached your free upload limit of {FREE_UPLOAD_LIMIT} videos."
        # For free users, creating the WorkoutSession object itself acts as incrementing the count!
        return True, None
    
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
        if remaining_seconds <= 0:
            return False, "You have exhausted your live coach time for this billing period."

        seconds_to_record = min(seconds_used, remaining_seconds)
        locked_subscription.live_coach_seconds_used = F("live_coach_seconds_used") + seconds_to_record
        locked_subscription.save(update_fields=["live_coach_seconds_used"])

    return True, None