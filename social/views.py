from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Friendship, Thread, Message
from .serializers import FriendshipSerializer, MessageSerializer, ThreadSerializer

User = get_user_model()

@login_required
def social_dashboard_view(request):
    """
    Renders the dedicated social circle hub (templates/social/friends_list.html).
    All friends parsing and search queries are offloaded to async fetch endpoints.
    """
    return render(request, 'social/friends_list.html')

@login_required
def direct_chat_suite_view(request, thread_uuid=None):
    """
    Renders the isolated full-height messaging workspace.
    Optionally accepts a thread_uuid directly to trigger an auto-connection pipeline.
    """
    context = {
        'initial_thread_uuid': str(thread_uuid) if thread_uuid else ''
    }
    return render(request, 'social/messages_suite.html', context)

# @login_required
# def chat_test_room(request, thread_uuid):
#     """
#     Renders a simple HTML testing template to execute live WebSocket operations
#     against a target chat thread room.
#     """
#     return render(request, 'social/chat_test.html', {'thread_uuid': thread_uuid})

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
        # Fetch relationships where current user is either sender or receiver
        # AND the relationship is either active ('accepted') or waiting confirmation ('pending')
        friendships = Friendship.objects.filter(
            Q(sender=request.user) | Q(receiver=request.user),
            status__in=['accepted', 'pending']
        ).select_related('sender', 'receiver')

        serializer = FriendshipSerializer(friendships, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChatThreadViewSet(viewsets.ViewSet):
    """ViewSet for managing chat threads and message history."""
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request):
        """
        POST /api/social/chat/
        NOTE: Since this is registered to a router, the default base URL for 
        creating an item is the root path of the endpoint, NOT /threads/.
        """
        target_username = request.data.get('username')
        if not target_username:
            return Response({"error": "Target username required"}, status=status.HTTP_400_BAD_REQUEST)
            
        target_user = get_object_or_404(User, username__iexact=target_username)
        
        # Check if a 1-on-1 thread already exists between these users
        thread = Thread.objects.filter(is_group=False, participants=request.user).filter(participants=target_user).first()
        
        if not thread:
            thread = Thread.objects.create(is_group=False)
            thread.participants.set([request.user, target_user])
            
        serializer = ThreadSerializer(thread)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def list(self, request):
        """
        GET /api/social/chat/
        Replaces the old @action(url_path='threads') with DRF's native list handler.
        """
        threads = Thread.objects.filter(participants=request.user).prefetch_related('participants', 'messages').order_by('-updated_at')
        serializer = ThreadSerializer(threads, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='history')
    def get_chat_history(self, request, pk=None):
        """GET /api/social/chat/<thread_uuid>/history/"""
        thread = get_object_or_404(Thread, id=pk, participants=request.user)
        messages = Message.objects.filter(thread=thread).order_by('-created_at')[:50]        
        messages = list(reversed(messages))
        
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)