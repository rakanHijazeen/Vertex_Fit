import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Thread, Message
from .serializers import MessageSerializer

class RealTimeChatConsumer(AsyncWebsocketConsumer):
    """
    Handles active WebSocket connections for real-time messaging between users.
    
    This consumer:
    - Authenticates the user from the connection scope.
    - Restricts access to participants of the requested thread.
    - Manages join/leave logic for Channels groups on Redis.
    - Non-disruptively commits incoming messages to the DB and broadcasts them.
    """
    async def connect(self):
        """
        Triggers on initial handshake. Verifies authentication and membership 
        before accepting the socket connection.
        """
        # Retrieve the user object populated by the AuthMiddlewareStack
        self.user = self.scope.get("user", AnonymousUser())
        
        # Security Gate: Reject unauthenticated connections early
        if isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            await self.close(code=4003)  # Forbidden
            return

        # 2. Extract the Thread UUID from the URL path pattern
        self.thread_id = self.scope["url_route"]["kwargs"]["thread_uuid"]
        self.room_group_name = f"chat_{self.thread_id}"

        # 3. Security Boundary: Verify user actually belongs to this conversation room
        is_participant = await self.verify_thread_membership()
        if not is_participant:
            await self.close(code=4003)
            return

        # Join the unique communication channel group inside Redis
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        # Accept the connection
        await self.accept()

    async def disconnect(self, close_code):
        """
        Triggers when the socket is closed. Cleans up Redis tracking entries.
        """
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """
        Invoked when the browser client sends a text frame over the WebSocket.
        Parses, validates, saves, and broadcasts the incoming message.
        """
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        message_text = data.get("message", "").strip()
        if not message_text:
            return  # Ignore blank payloads

        # Save message to database asynchronously without blocking the main event loop
        message_obj = await self.save_message_to_db(message_text)

        # Broadcast the message payload to everyone currently tuned into this room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat_message", # # Directs Channels to invoke the 'chat_message' method
                "message_payload": message_obj
            }
        )

    async def chat_message(self, event):
        """
        Receive helper method triggered by the group broadcast. 
        Pushes the serialized message payload straight to the client browser.
        """
        payload = event["message_payload"]
        await self.send(text_data=json.dumps(payload))

    # --- Database Sync to Async Workers ---

    @database_sync_to_async
    def verify_thread_membership(self):
        """
        Queries the database to confirm if the connecting user is an active 
        participant of the specified Thread.
        """
        return Thread.objects.filter(id=self.thread_id, participants=self.user).exists()

    @database_sync_to_async
    def save_message_to_db(self, text):
        """
        Persists the message to PostgreSQL, bumps the thread's updated timestamp 
        to bubble it up in active chats, and returns the serialized payload.
        """
        thread_instance = Thread.objects.get(id=self.thread_id)
        
        # Create message record
        message = Message.objects.create(
            thread=thread_instance,
            sender=self.user,
            text=text
        )
        
        # Touch the thread's updated_at timestamp so it bubbles up to the top of chat list feeds
        thread_instance.save()
        
        # 1. Serialize the message object into a dict
        raw_data = MessageSerializer(message).data
        
        # 2. Convert UUIDs, Datetimes, etc., to JSON-safe strings before shipping to msgpack
        safe_data = json.loads(json.dumps(raw_data, default=str))

        # Serialize the message object into a clean dictionary
        return safe_data