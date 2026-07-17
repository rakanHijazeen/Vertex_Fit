import uuid
from django.db import models
from django.conf import settings

class Friendship(models.Model):
    """
    Tracks unidirectional and accepted social relationships between users.
    
    This acts as a junction table to map self-referencing relationships.
    To avoid redundant records and database bloat, uniqueness is enforced on
    the combination of sender and receiver.

    Key Relationships:
        * `sender`: The user who initiates the friend request (ForeignKey -> User).
        * `receiver`: The user who receives the friend request (ForeignKey -> User).
    
    States (`status`):
        * `pending`: Request sent; awaiting receiver's action.
        * `accepted`: Mutual connection established. Both users can message each other.
        * `blocked`: Unidirectional lock preventing further requests/messages.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('blocked', 'Blocked'),
    ]

    # The user who initiates the friend request
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_friendships',
        help_text="The user initiating the friendship request."
    )
    # The user receiving the friend request
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_friendships',
        help_text="The user receiving the friendship request."
    )
    status = models.CharField(
        max_length=10, 
        choices=STATUS_CHOICES, 
        default='pending',
        help_text="The current state of the relationship."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Enforce that only one relationship record can exist between any two specific users
        unique_together = ('sender', 'receiver')
        # Speeds up user friendship status lookups and listing queries on the index
        indexes = [
            models.Index(fields=['sender', 'receiver', 'status']),
        ]

    def __str__(self):
        return f"{self.sender.username} -> {self.receiver.username} ({self.status})"


class Thread(models.Model):
    """
    Represents a unique communication channel (chat room) between participants.
    
    Supports both direct messaging (1-on-1) and group chats. The model uses 
    UUIDs as primary keys instead of incremental integers to secure endpoints
    against URL enumeration scanning.

    Key Relationships:
        * `participants`: A Many-to-Many field linking users associated with this thread.
          Accessing a user's threads can be done via the `chat_threads` related name.
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False, 
        help_text="Secure, non-sequential unique identifier for the chat thread."
    )

    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        related_name='social_direct_threads', # differentiates from other LLM-related fields in the User model
        help_text="Users belonging to this conversation."
    )

    is_group = models.BooleanField(default=False, help_text="Designates whether this thread is a group chat with multiple users.")
    name = models.CharField(max_length=255, blank=True, null=True, help_text="Optional name for the thread, primarily utilized for group chats.")  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.is_group and self.name:
            return f"Group Chat: {self.name}"
        return f"Direct Chat ({self.id})"


class Message(models.Model):
    """
    Stores individual textual messages sent within an active chat thread.
    
    Messages are ordered by their creation time. An index is applied across
    the thread ID and timestamp fields to optimize paginated historical loads.

    Key Relationships:
        * `thread`: The conversation channel to which this message belongs (ForeignKey -> Thread).
        * `sender`: The user who wrote and sent the message (ForeignKey -> User).
    """
    thread = models.ForeignKey(
        Thread, 
        on_delete=models.CASCADE, 
        related_name='messages',
        help_text="The parent thread context of this message."
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_messages',
        help_text="The user who sent this message."
    )
    text = models.TextField( help_text="The content of the message." )
    is_read = models.BooleanField(default=False, help_text="Indicates whether the message has been read by the recipient.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            # Speeds up message history loading for active threads
            models.Index(fields=['thread', 'created_at']),
        ]

    def __str__(self):
        return f"Message by {self.sender.username} in Thread {self.thread.id}"