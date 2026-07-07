from django.db import models
from django.conf import settings

class Exercise(models.Model):
    """Static repository look-up table for baseline tracking movements."""
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Squat, Bicep Curl")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Anchor joint index for MediaPipe keypoint tracking (e.g., 16=Wrist, 24=Hip)
    anchor_joint = models.IntegerField(default=24, help_text="MediaPipe keypoint node index")
    # If true, evaluate horizontal (X) motion instead of vertical (Y)
    track_horizontally = models.BooleanField(default=False, help_text="If true, track X-axis motion for rep detection")
    # Secondary MediaPipe node index to use when the primary anchor becomes occluded/unreliable
    fallback_anchor_joint = models.IntegerField(blank=True, null=True, help_text="Optional fallback node index when the primary anchor is occluded")
    def __str__(self):
        return self.name


class WorkoutSession(models.Model):
    """Transactional data capturing live performance execution metrics and AI feedback."""
    
    # Explicit status state tracking matrix for background async execution (Phase 4.3)
    STATUS_CHOICES = [
        ('pending', 'Analyzing Form...'),
        ('completed', 'Analysis Complete'),
        ('failed', 'Analysis Failed'),
    ]

    id = models.BigAutoField(primary_key=True)
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='workout_sessions'
    )
    exercise = models.ForeignKey(
        Exercise, 
        on_delete=models.PROTECT, 
        related_name='sessions'
    )
    
    rep_count = models.PositiveIntegerField(default=0)
    video_url = models.URLField(max_length=500, blank=True, null=True, help_text="S3 source link")
    vlm_feedback = models.TextField(blank=True, null=True, help_text="AI system performance breakdown")
    report_language = models.CharField(max_length=10, default='English')
    
    # The status tracking flag added to satisfy Phase 4 requirements
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Tracks the backend analysis execution state cycle"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.exercise.name} ({self.timestamp.strftime('%Y-%m-%d')}) [{self.status}]"