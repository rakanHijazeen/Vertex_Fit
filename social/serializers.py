from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Friendship, Thread, Message

User = get_user_model()

class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal user data required for social listings."""
    class Meta:
        model = User
        fields = ['id', 'username']


class FriendshipSerializer(serializers.ModelSerializer):
    '''Serializer for the Friendship model, providing a concise representation of user relationships.'''
    sender = UserSummarySerializer(read_only=True)
    receiver = UserSummarySerializer(read_only=True)

    class Meta:
        model = Friendship
        fields = ['id', 'sender', 'receiver', 'status', 'created_at', 'updated_at']
        read_only_fields = ['status']


class ThreadSerializer(serializers.ModelSerializer):
    '''Serializer for the Thread model, representing a conversation between users.'''
    participants = UserSummarySerializer(many=True, read_only=True)
    latest_message = serializers.SerializerMethodField()

    class Meta:
        model = Thread
        fields = ['id', 'participants', 'is_group', 'name', 'latest_message', 'updated_at']

    def get_latest_message(self, obj):
        """Retrieves the text of the most recent message in this conversation."""
        latest = obj.messages.order_by('-created_at').first() 
        if latest:
            return {
                'text': latest.text,
                'sender': latest.sender.username,
                'created_at': latest.created_at
            }
        return None
    
class MessageSerializer(serializers.ModelSerializer):
    """Serializer for the Message model, representing individual messages within a conversation."""
    sender_username = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'thread', 'sender', 'sender_username', 'text', 'is_read', 'created_at']
        read_only_fields = ['id', 'sender', 'created_at']