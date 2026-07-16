from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.db import transaction
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


class ProfileAccountSerializer(serializers.Serializer):
    """Combines User credentials and linked Profile fields for the profile page."""
    username = serializers.CharField(max_length=150, required=False, allow_blank=False)
    email = serializers.EmailField(required=False)
    gender = serializers.ChoiceField(choices=[('Male', 'Male'), ('Female', 'Female')], required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    height = serializers.FloatField(required=False, allow_null=True)
    target_weight = serializers.FloatField(required=False, allow_null=True)
    fitness_goal = serializers.ChoiceField(choices=Profile.FITNESS_GOALS, required=False)
    experience_level = serializers.ChoiceField(
        choices=[('BEGINNER', 'Beginner'), ('INTERMEDIATE', 'Intermediate'), ('ADVANCED', 'Advanced')],
        required=False
    )
    timezone = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def to_representation(self, instance):
        profile = instance.profile
        return {
            'username': instance.username,
            'email': instance.email,
            'gender': profile.gender,
            'date_of_birth': profile.date_of_birth,
            'height': profile.height,
            'target_weight': profile.target_weight,
            'fitness_goal': profile.fitness_goal,
            'experience_level': profile.experience_level,
            'timezone': profile.timezone,
            'is_email_verified': profile.is_email_verified,
            'onboarding_complete': profile.onboarding_complete,
        }

    def validate(self, attrs):
        user = self.instance
        if user is None:
            return attrs

        is_oauth_user = bool(self.context.get('is_oauth_user', False))

        if 'username' in attrs and attrs['username'] != user.username:
            if is_oauth_user:
                raise serializers.ValidationError({'username': 'OAuth accounts cannot change their username.'})
            if User.objects.exclude(pk=user.pk).filter(username__iexact=attrs['username']).exists():
                raise serializers.ValidationError({'username': 'This username is already taken.'})

        if 'email' in attrs and attrs['email'] != user.email:
            if is_oauth_user:
                raise serializers.ValidationError({'email': 'OAuth accounts cannot change their email address.'})
            if User.objects.exclude(pk=user.pk).filter(email__iexact=attrs['email']).exists():
                raise serializers.ValidationError({'email': 'This email address is already in use.'})

        return attrs

    @transaction.atomic
    def update(self, instance, validated_data):
        request = self.context.get('request')
        user = instance
        profile = user.profile

        email_changed = False

        if 'username' in validated_data and validated_data['username'] != user.username:
            user.username = validated_data['username']

        if 'email' in validated_data and validated_data['email'] != user.email:
            user.email = validated_data['email']
            email_changed = True

        profile_fields = [
            'gender',
            'date_of_birth',
            'height',
            'target_weight',
            'fitness_goal',
            'experience_level',
            'timezone',
        ]
        for field_name in profile_fields:
            if field_name in validated_data:
                setattr(profile, field_name, validated_data[field_name])

        if email_changed:
            profile.is_email_verified = False

        user.save()
        profile.save()

        if email_changed and request is not None:
            from .utils import send_verification_email

            def _send_profile_verification():
                try:
                    send_verification_email(user, request)
                except Exception:
                    pass

            transaction.on_commit(_send_profile_verification)

        return user

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