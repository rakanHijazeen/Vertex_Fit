from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

class PlanTier(models.TextChoices):
    FREE = 'free', 'Free'
    PRO = 'pro', 'Pro'
    VIP = 'vip', 'VIP'


class BillingCycle(models.TextChoices):
    MONTHLY = 'monthly', 'Monthly'
    YEARLY = 'yearly', 'Yearly'


class UserSubscription(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    
    # Tier & Billing Info
    tier = models.CharField(
        max_length=10,
        choices=PlanTier.choices,
        default=PlanTier.FREE
    )
    billing_cycle = models.CharField(
        max_length=10,
        choices=BillingCycle.choices,
        default=BillingCycle.MONTHLY
    )
    
    # Paddle Identifiers
    paddle_customer_id = models.CharField(max_length=255, blank=True, null=True)
    paddle_subscription_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    price_id = models.CharField(max_length=255, blank=True, null=True)
    
    # Status & Validity Period
    status = models.CharField(max_length=50, default='active')  # e.g., active, trialing, past_due, canceled
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    # Monthly Usage Trackers (Reset monthly)
    live_coach_seconds_used = models.PositiveIntegerField(
        default=0, 
        help_text="Tracks live AI voice coaching consumption in seconds."
    )
    retroactive_uploads_count = models.PositiveIntegerField(
        default=0, 
        help_text="Tracks retroactive video uploads processed this month."
    )
    last_usage_reset = models.DateTimeField(default=timezone.now)

    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        try:
            tier_label = PlanTier(self.tier).label
        except ValueError:
            tier_label = self.tier
        return f"{self.user.username} - {tier_label} ({self.status})"

    # --- Feature Enforcement & Limit Helpers ---

    @property
    def live_coach_minute_limit(self) -> int:
        """Returns max voice coaching minutes allowed per month."""
        limits = {
            PlanTier.FREE.value: 3,
            PlanTier.PRO.value: 45,
            PlanTier.VIP.value: 120,
        }

        return limits.get(str(self.tier), 3)

    @property
    def live_coach_seconds_remaining(self) -> int:
        """Returns remaining live coach time in seconds."""
        self.reset_usage_if_needed() # Ensure usage is up-to-date before calculating remaining time
        max_seconds = self.live_coach_minute_limit * 60
        return max(0, max_seconds - self.live_coach_seconds_used)

    @property
    def can_use_live_coach(self) -> bool:
        """Checks if the user has remaining minutes for live coaching."""
        return self.live_coach_seconds_remaining > 0

    @property
    def retroactive_upload_limit(self) -> int | None:
        """Returns upload limit per month. Returns None for unlimited tiers."""
        if self.tier in [PlanTier.PRO.value, PlanTier.VIP.value]:
            return None  # Unlimited
        return 3

    @property
    def can_upload_retroactive_video(self) -> bool:
        """Checks if the user can perform a retroactive video upload."""
        limit = self.retroactive_upload_limit
        if limit is None:
            return True
        return self.retroactive_uploads_count < limit

    @property
    def has_ads(self) -> bool:
        """Free tier experiences ads; Pro and VIP are ad-free."""
        return self.tier == PlanTier.FREE.value

    @property
    def has_deep_context_ai_chat(self) -> bool:
        """Pro and VIP unlock deep biometric & history context for AI chat."""
        return self.tier in [PlanTier.PRO.value, PlanTier.VIP.value]

    @property
    def has_priority_upload_queue(self) -> bool:
        """VIP users get priority queue processing for retroactive uploads."""
        return self.tier == PlanTier.VIP.value

    # --- Reset Utility ---

    def reset_usage_if_needed(self):
        """
        Resets monthly usage counters if the current time has crossed 
        the current billing period end or 30 days since last reset.
        """
        now = timezone.now()
        
        # Check if we crossed current_period_end (if set), otherwise fallback to 30 days
        if self.current_period_end and now >= self.current_period_end:
            should_reset = True
        else:
            # Fallback for free tiers or subscriptions without explicit end dates
            should_reset = now >= (self.last_usage_reset + timedelta(days=30))

        if should_reset:
            self.live_coach_seconds_used = 0
            self.retroactive_uploads_count = 0
            self.last_usage_reset = now
            self.save(update_fields=[
                'live_coach_seconds_used', 
                'retroactive_uploads_count', 
                'last_usage_reset'
            ])