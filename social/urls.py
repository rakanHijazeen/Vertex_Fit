from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FriendshipViewSet, ChatThreadViewSet

router = DefaultRouter()
router.register(r'friends', FriendshipViewSet, basename='friends')
router.register(r'chat', ChatThreadViewSet, basename='chat')

urlpatterns = [
    path('', include(router.urls)),
]