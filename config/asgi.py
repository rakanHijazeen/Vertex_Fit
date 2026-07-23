"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application

# 1. Set environment variable FIRST
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# 2. Initialize Django ASGI app BEFORE importing Channels modules or routing
django_asgi_app = get_asgi_application()

# 3. Import Channels modules AFTER Django initialized
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from workouts.routing import websocket_urlpatterns as workout_urls
import social.routing

# Cleanly combine both lists of routing patterns into a single unified workspace list
combined_websocket_urls = workout_urls + social.routing.websocket_urlpatterns

# 4. Pass pre-initialized django_asgi_app to ProtocolTypeRouter
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    # WebSocket handler for live coaching, personalized chat, and real-time social messaging
    "websocket": AuthMiddlewareStack(
        URLRouter(combined_websocket_urls)
    ),
})