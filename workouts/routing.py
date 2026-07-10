# VERTEX_FIT/workouts/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Match the connection endpoint explicitly initialized in your JS file
    re_path(r'^ws/live-coaching/?$', consumers.LiveCoachingConsumer.as_asgi()),
    # new personalized dashboard text chatbot route
    re_path(r'^ws/chat/?$', consumers.PersonalChatConsumer.as_asgi()),
]