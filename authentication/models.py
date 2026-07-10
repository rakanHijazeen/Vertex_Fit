from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager

class CustomUserManager(BaseUserManager):
    """Custom manager where email is the unique identifier for auth."""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        
        email = self.normalize_email(email)
        
        # Enforce that username is explicitly popped out of extra_fields if passed
        extra_fields.pop('username', None) 
        
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model expanding fields for authentication handles."""
    username = None  # Removes the default username field completely
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

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
    is_premium = models.BooleanField(default=False)
    paddle_subscription_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Profile for {self.user.email}"