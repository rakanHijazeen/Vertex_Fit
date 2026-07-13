from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import Profile

User = get_user_model()

class Phase1RegistrationSerializer(serializers.ModelSerializer):
    """Handles Phase 1: Validating credentials and creating the User base account."""
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'username', 'password']  # Added username explicitly

    def create(self, validated_data):
        # Custom user manager handles normalization, hashing, and database indexing
        return User.objects.create_user(
            email=validated_data['email'],
            username=validated_data['username'],
            password=validated_data['password']
        )


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """Handles Phase 2: Updating user fitness metrics and onboarding status."""
    class Meta:
        model = Profile
        fields = [
            'gender', 'date_of_birth', 'height', 'target_weight', 
            'fitness_goal', 'experience_level', 'timezone'
        ]
        extra_kwargs = {
            'gender': {'required': True},
            'height': {'required': True},
            'target_weight': {'required': True},
            'fitness_goal': {'required': True},
        }

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Dynamically remaps the username requirement to handle email or username text inputs."""
    login_identifier = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically clear whatever base field SimpleJWT is expecting (username or email)
        self.fields.pop(self.username_field, None)
        self.fields.pop('username', None)

    def validate(self, attrs):
        # Map the frontend string directly to what the auth backend expects
        identifier = attrs.get('login_identifier')
        
        # SimpleJWT looks up credentials using self.username_field key
        attrs[self.username_field] = identifier
        attrs['username'] = identifier
        
        return super().validate(attrs)