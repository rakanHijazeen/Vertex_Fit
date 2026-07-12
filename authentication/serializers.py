from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Profile

User = get_user_model()

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = ['gender','date_of_birth', 'height', 'target_weight', 'fitness_goal']


class RegistrationSerializer(serializers.ModelSerializer):
    # Nest the profile fields inside the registration payload
    profile = ProfileSerializer(required=False)
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'password', 'profile']

    def create(self, validated_data):
        profile_data = validated_data.pop('profile', {})
        
        # Enforce an atomic transaction context block
        with transaction.atomic():
            # Create the custom user instance using our manager
            user = User.objects.create_user(
                email=validated_data['email'],
                password=validated_data['password']
            )
            # Build the corresponding profile linked via OneToOne
            Profile.objects.create(user=user, **profile_data)
            
        return user