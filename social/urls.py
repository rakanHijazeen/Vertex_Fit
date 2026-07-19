from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FriendshipViewSet, ChatThreadViewSet
from social import views

router = DefaultRouter()
router.register(r'friends', FriendshipViewSet, basename='friends')
router.register(r'chat', ChatThreadViewSet, basename='chat')

urlpatterns = [
    path('', include(router.urls)),
    
    # The template route for managing friends, searching users, and checking your status
    path('hub/', views.social_dashboard_view, name='social_dashboard'),
    
    path('messaging/suite/', views.direct_chat_suite_view, name='direct_chat_suite'),
    path('messaging/suite/<uuid:thread_uuid>/', views.direct_chat_suite_view, name='direct_chat_suite_explicit'),

    # API Router Inclusion
    path('', include(router.urls)),
]