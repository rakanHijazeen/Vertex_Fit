from django.contrib import admin
from .models import Exercise, WorkoutSession

@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'exercise', 'rep_count', 'timestamp')
    list_filter = ('exercise', 'timestamp')
    search_fields = ('user__email', 'exercise__name')