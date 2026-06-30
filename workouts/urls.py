from django.urls import path
from .views import WorkoutVideoUploadView 

urlpatterns = [
    # Django appends this to 'api/workouts/' automatically!
    path('upload/', WorkoutVideoUploadView.as_view(), name='workout_video_upload'),
]