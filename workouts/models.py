from django.db import models
from django.conf import settings

class Exercise(models.Model):
    """Static repository look-up table for baseline tracking movements."""
    name = models.CharField(max_length=100, unique=True, help_text="e.g., Squat, Bicep Curl")
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class WorkoutSession(models.Model):
    """Transactional data capturing live performance execution metrics and AI feedback."""
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
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.exercise.name} ({self.timestamp.strftime('%Y-%m-%d')})"