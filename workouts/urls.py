from django.urls import path
from workouts import views
from .views import (
    GetOrCreateChatThreadAPIView,
    GetChatHistoryAPIView,
    WorkoutVideoUploadView, 
    WorkoutSessionDetailView, 
    live_tracker_view,
    workout_analysis_page_view
)

urlpatterns = [
    # 1. Existing REST API endpoints utilized by JavaScript fetch workflows
    path('upload/', WorkoutVideoUploadView.as_view(), name='workout_video_upload'),
    # CASE 1: Fetches the entire history list (Used by dashboard.html fetch request)
    path('api/sessions/', WorkoutSessionDetailView.as_view(), name='api_session_list'),
    
    # CASE 2: Fetches single video analytics detail by ID
    path('session/<int:session_id>/', WorkoutSessionDetailView.as_view(), name='workout_session_detail'),

    # 2. Production View layout targeting the PWA interface template
    path('tracker/', live_tracker_view, name='live_workout_tracker'),
    
    # 3. The dedicated HTML page to display the deep post-set analysis
    path('session/<int:session_id>/analysis/', workout_analysis_page_view, name='workout_analysis_page'),
    # 4. Dashboard index log feed
    path('dashboard/', views.workout_dashboard, name='workout_dashboard'),
    # 5. Chat thread initialization endpoint for the personalized AI assistant
    path('chat/thread/', GetOrCreateChatThreadAPIView.as_view(), name='chat_thread_init'),
    # 6. AI chat coach view
    path('chat/', views.ai_chat_coach_view, name='ai_chat_coach'),
    # 7. API endpoint to fetch historical chat messages for a given thread
    path('chat/history/<int:thread_id>/', GetChatHistoryAPIView.as_view(), name='chat_history_api'),
]