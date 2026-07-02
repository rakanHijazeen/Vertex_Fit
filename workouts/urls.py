from django.urls import path
from .views import WorkoutVideoUploadView, WorkoutSessionDetailView, live_tracker_view

urlpatterns = [
    # 1. Existing REST API endpoints utilized by JavaScript fetch workflows
    path('upload/', WorkoutVideoUploadView.as_view(), name='workout_video_upload'),
    path('session/<int:session_id>/', WorkoutSessionDetailView.as_view(), name='workout_session_detail'),
    
    # 2. Production View layout targeting the PWA interface template
    path('tracker/', live_tracker_view, name='live_workout_tracker'),
]