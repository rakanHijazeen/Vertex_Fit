from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager

class CustomUserManager(BaseUserManager):
    """Custom manager where email is the unique identifier for auth."""
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        if not username:
            raise ValueError('The Username field must be set')
        
        email = self.normalize_email(email) 
        
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)


class User(AbstractUser):
    """Custom user model expanding fields for authentication handles."""
    username = models.CharField(
        max_length=150, 
        unique=True,          # Setting unique=True AUTOMATICALLY creates a database index in PostgreSQL!
        db_index=True,        # Explicitly keeping this here for absolute clarity 
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
    )
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']  # 4. Tells Django that username is required when creating users/superusers via terminal
    
    objects = CustomUserManager()

    def __str__(self):
        return self.email


class Profile(models.Model):
    """Profile table tracking bio metrics and structural fitness data."""
    FITNESS_GOALS = [
        ('BULK', 'Bulking / Gain Muscle'),
        ('CUT', 'Cutting / Lose Fat'),
        ('MAINTAIN', 'Maintenance'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female')], null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    height = models.FloatField(help_text="Height in cm", null=True, blank=True)
    target_weight = models.FloatField(help_text="Target weight in kg", null=True, blank=True)
    fitness_goal = models.CharField(max_length=12, choices=FITNESS_GOALS, default='MAINTAIN')
    experience_level = models.CharField(max_length=20, choices=[('BEGINNER', 'Beginner'), ('INTERMEDIATE', 'Intermediate'), ('ADVANCED', 'Advanced')], default='BEGINNER')
    timezone = models.CharField(max_length=50, default='Asia/Amman') # Default timezone set to Asia/Amman
    is_premium = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    paddle_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    onboarding_complete = models.BooleanField(default=False) # tracks if the user has completed the onboarding registration process

    def __str__(self):
        return f"Profile for {self.user.email}"