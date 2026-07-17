from django.contrib import admin
from .models import Thread, Message, Friendship

@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'updated_at')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'thread', 'sender', 'created_at')

@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    # Helps you track relationship status at a glance
    list_display = ('id', 'sender', 'receiver', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('sender__username', 'receiver__username')