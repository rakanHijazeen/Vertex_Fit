from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

User = get_user_model()

class MySocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Invoked just before connecting a social account. 
        If the email already exists, we link the social account to the existing user.
        """
        # 1. Skip if the social login is already linked
        if sociallogin.is_existing:
            return

        # 2. Get the email from Google's social payload
        email = sociallogin.user.email
        if not email:
            return

        # 3. Handle conflict resolution dynamically
        try:
            # Query case-insensitively since the system supports case-insensitive logins
            existing_user = User.objects.get(email__iexact=email)
            
            # Link the new social account credentials with the existing user
            sociallogin.connect(request, existing_user)
        except User.DoesNotExist:
            # If the user doesn't exist, proceed with creating a fresh account
            pass