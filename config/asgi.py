"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from workouts.routing  import websocket_urlpatterns as workout_urls
import social.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Cleanly combine both lists of routing patterns into a single unified workspace list
combined_websocket_urls = workout_urls + social.routing.websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # WebSocket handler for live coaching, personalized chat, and real-time social messaging
    "websocket": AuthMiddlewareStack(
        URLRouter(combined_websocket_urls)
    ),
})