from django.urls import re_path
from . import consumers

# Defines URL patterns routed directly to WebSocket consumers.
# Matches: ws/social/chat/<uuid-string>/
websocket_urlpatterns = [
    re_path(
        r'^ws/social/chat/(?P<thread_uuid>[0-9a-f-]+)/$', 
        consumers.RealTimeChatConsumer.as_asgi(),
        name='social-chat-ws'
    ),
]