from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Friendship, Thread, Message
from .serializers import FriendshipSerializer, MessageSerializer, ThreadSerializer

User = get_user_model()

class FriendshipViewSet(viewsets.ViewSet):
    """ViewSet for managing friendship requests and relationships."""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='request')
    def send_request(self, request):
        """POST /api/social/friends/request/"""
        receiver_username = request.data.get('username')
        if not receiver_username:
            return Response({"error": "Username field is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        if receiver_username.lower() == request.user.username.lower():
            return Response({"error": "You cannot send a friend request to yourself."}, status=status.HTTP_400_BAD_REQUEST)

        receiver = get_object_or_404(User, username__iexact=receiver_username)

        # Check for an existing relationship in either direction
        existing = Friendship.objects.filter(
            (Q(sender=request.user, receiver=receiver) | Q(sender=receiver, receiver=request.user))
        ).first()

        if existing:
            return Response(
                {"error": f"A relationship status of '{existing.status}' already exists with this user."},
                status=status.HTTP_400_BAD_REQUEST
            )

        friendship = Friendship.objects.create(sender=request.user, receiver=receiver, status='pending')
        serializer = FriendshipSerializer(friendship)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='respond')
    def respond_to_request(self, request):
        """POST /api/social/friends/respond/"""
        friendship_id = request.data.get('friendship_id')
        action_choice = request.data.get('action')  # Expected: 'accept', 'decline', 'block'

        if action_choice not in ['accept', 'decline', 'block']:
            return Response({"error": "Invalid action. Choose 'accept', 'decline', or 'block'."}, status=status.HTTP_400_BAD_REQUEST)

        # Retrieve friendship record where current user is the target receiver
        friendship = get_object_or_404(Friendship, id=friendship_id, receiver=request.user)

        if action_choice == 'accept':
            friendship.status = 'accepted'
            friendship.save()

            # Architectural Hook: Instantly provision a conversation Thread upon connection confirmation
            thread, created = Thread.objects.get_or_create(is_group=False)
            if created:
                thread.participants.set([friendship.sender, friendship.receiver])

            return Response({"message": "Friend request accepted. Chat room provisioned."}, status=status.HTTP_200_OK)

        elif action_choice == 'decline':
            friendship.delete()  # Clean removal from table allows them to request again later
            return Response({"message": "Friend request declined."}, status=status.HTTP_200_OK)

        elif action_choice == 'block':
            friendship.status = 'blocked'
            friendship.save()
            return Response({"message": "User has been blocked."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='list')
    def list_friends(self, request):
        """GET /api/social/friends/list/"""
        # Fetch relationships where current user is either sender or receiver and status is accepted
        friendships = Friendship.objects.filter(
            (Q(sender=request.user) | Q(receiver=request.user)),
            status='accepted'
        ).select_related('sender', 'receiver')  # Optimization: Join tables to prevent N+1 hits

        serializer = FriendshipSerializer(friendships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChatThreadViewSet(viewsets.ViewSet):
    """ViewSet for managing chat threads and message history."""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='threads')
    def list_threads(self, request):
        """GET /api/social/chat/threads/"""
        threads = Thread.objects.filter(participants=request.user).prefetch_related('participants', 'messages').order_by('-updated_at')
        serializer = ThreadSerializer(threads, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # This endpoint retrieves the last 50 messages in a specific chat thread, ensuring the requesting user is a participant.
    @action(detail=True, methods=['get'], url_path='history')
    def get_chat_history(self, request, pk=None):
        """GET /api/social/chat/<thread_uuid>/history/"""
        # Ensure the requesting user belongs to the conversation room
        thread = get_object_or_404(Thread, id=pk, participants=request.user)
        
        # Pull the last 50 historical messages
        # Optimization: We already indexed ('thread', 'created_at') in our model!
        messages = Message.objects.filter(thread=thread).order_by('-created_at')[:50]        
        
        # Reverse them so they show up in standard chronological order (oldest to newest)
        messages = list(reversed(messages))
        
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)