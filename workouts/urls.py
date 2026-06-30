from django.urls import path
from .views import WorkoutVideoUploadView 

urlpatterns = [
    path('upload/', WorkoutVideoUploadView.as_view(), name='workout_video_upload'),
]