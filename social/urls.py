from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FriendshipViewSet, ChatThreadViewSet
from social import views

router = DefaultRouter()
router.register(r'friends', FriendshipViewSet, basename='friends')
router.register(r'chat', ChatThreadViewSet, basename='chat')

urlpatterns = [
    path('', include(router.urls)),
    # Quick debug view for testing real-time pipelines manually
    path('test/chat/<str:thread_uuid>/', views.chat_test_room, name='chat-test'),
]