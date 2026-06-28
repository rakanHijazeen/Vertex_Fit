from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Profile

class CustomUserAdmin(UserAdmin):
    """Configuration to display and manage our email-driven user model."""
    list_display = ('email', 'is_staff', 'is_active', 'date_joined')
    ordering = ('email',)
    
    # Define fields to display when editing a user via admin panel
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    
    # These configurations let us use email during user creation panels
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password'),
        }),
    )
    search_fields = ('email',)

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Configuration to display user fitness metrics and monetization status."""
    list_display = ('user', 'fitness_goal', 'height', 'target_weight', 'is_premium')
    list_filter = ('fitness_goal', 'is_premium')
    search_fields = ('user__email',)

# Formally register the custom user model with its configuration matrix
admin.site.register(User, CustomUserAdmin)