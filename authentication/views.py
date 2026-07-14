from rest_framework import settings, status
from django.shortcuts import redirect, render
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import Phase1RegistrationSerializer, ProfileUpdateSerializer, CustomTokenObtainPairSerializer
from django.contrib.auth import login, logout, get_user_model, authenticate
from .models import Profile, User
from django.contrib.auth.models import User
import traceback
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.contrib import messages
from .utils import signer, TOKEN_MAX_AGE, SignatureExpired, BadSignature, send_verification_email

def login_page(request):
    """Renders the login page template for the web interface."""
    return render(request, 'authentication/login.html')

def signup_page(request):
    """Renders the signup page template for the web interface."""
    return render(request, 'authentication/signup.html')

def onboarding_page(request):
    return render(request, 'authentication/onboarding.html')

def landing_page(request):
    if request.user.is_authenticated:
        return redirect('/api/workouts/dashboard/') # Go straight to dashboard if already logged in[cite: 1]
    return render(request, 'base.html')

# Safely extract SimpleJWT settings from settings.py dynamically to bypass static type-checking issues
JWT_SETTINGS = getattr(settings, 'SIMPLE_JWT', {})


@method_decorator(csrf_exempt, name='dispatch')
class RegistrationAPIView(APIView):
    """
    Phase 1 Registration:
    Creates user account with email, username, and password, builds an incomplete profile,
    and returns initial HttpOnly JWT/Session credentials.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = Phase1RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                # Create user base account
                user: User = serializer.save()
                
                # Initialize an incomplete profile stub automatically
                # Stays complete=False until phase 2 data is submitted
                Profile.objects.create(user=user, onboarding_complete=False)
            
            # Set the backend attribute to point to your custom backend class
            user.backend = 'authentication.views.EmailOrUsernameModelBackend'

            # 2. TRIGGER VERIFICATION EMAIL
            # We wrap this in a try/except block so that even if the email API experiences a 
            # temporary network hiccup, it won't crash the user's registration experience.
            try:
                send_verification_email(user, request)  # Send verification email to the user
            except Exception as e:
                print("--- EMAIL SENDING FAILED ---")
                traceback.print_exc()
            # Log the user into standard Django session for template views / Channels
            login(request, user)
            
            # Programmatically generate JWT tokens for the newly registered user
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            
            response = Response({
                "message": "Phase 1 complete. Core identity created successfully.",
                "requires_onboarding": True,
                "access": access_token  # Return access token to be kept in frontend JS memory
            }, status=status.HTTP_201_CREATED)
            
            # Address dynamic secure cookie flag to prevent browser drop in local HTTP dev
            secure_cookie = JWT_SETTINGS.get('AUTH_COOKIE_SECURE', False) and request.is_secure()
            
            # Drop the long-lived refresh token directly into the browser's encrypted cookie jar
            response.set_cookie(
                key=JWT_SETTINGS.get('AUTH_COOKIE', 'refresh_token'),
                value=str(refresh),
                expires=JWT_SETTINGS.get('REFRESH_TOKEN_LIFETIME'),
                secure=secure_cookie,
                httponly=JWT_SETTINGS.get('AUTH_COOKIE_HTTP_ONLY', True),
                path=JWT_SETTINGS.get('AUTH_COOKIE_PATH', '/api/auth/'),
                samesite=JWT_SETTINGS.get('AUTH_COOKIE_SAMESITE', 'Lax')
            )
            return response
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileUpdateAPIView(APIView):
    """
    Phase 2 Registration:
    Collects health metrics, fitness targets, and local time tracking parameters 
    to finalize onboarding access locks.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        # Extract user's pre-built template profile row
        profile = request.user.profile
        
        serializer = ProfileUpdateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            # Commit incoming physical stats and mark onboarding as complete
            serializer.save(onboarding_complete=True)
            return Response({
                "message": "Phase 2 complete. Biometric profile established successfully.",
                "onboarding_complete": True
            }, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LoginAPIView(TokenObtainPairView):
    """
    Production login endpoint that catches user credentials (username or email), 
    returns an access token to client runtime memory, and locks down the refresh 
    token inside an HttpOnly cookie.
    """
    serializer_class = CustomTokenObtainPairSerializer # Explicitly attach your new serializer

    def post(self, request, *args, **kwargs):
        # 1. Let SimpleJWT and your CustomTokenObtainPairSerializer handle the heavy lifting
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            
            # 2. Extract credentials from the request payload safely
            login_identifier = request.data.get('login_identifier', '').strip()
            password = request.data.get('password')

            # 3. Use authenticate() so your backend finds the user via email OR username
            user = authenticate(request, username=login_identifier, password=password)
            
            if user is not None:
                # Log the user into Django session context for template page access and WebSocket channels
                login(request, user)
            
            # Strip the refresh token out of the JSON response payload to isolate it from XSS surfaces
            response.data = {
                "message": "Authentication successful.",
                "access": access_token
            }
        
            secure_cookie = JWT_SETTINGS.get('AUTH_COOKIE_SECURE', False) and request.is_secure()
            
            # Encapsulate refresh token inside the secure browser cookie layer
            response.set_cookie(
                key=JWT_SETTINGS.get('AUTH_COOKIE', 'refresh_token'),
                value=refresh_token,
                expires=JWT_SETTINGS.get('REFRESH_TOKEN_LIFETIME'),
                secure=secure_cookie,
                httponly=JWT_SETTINGS.get('AUTH_COOKIE_HTTP_ONLY', True),
                path=JWT_SETTINGS.get('AUTH_COOKIE_PATH', '/api/auth/'),
                samesite=JWT_SETTINGS.get('AUTH_COOKIE_SAMESITE', 'Lax')
            )
        return response


class ProductionTokenRefreshAPIView(TokenRefreshView):
    """
    Extracts the HttpOnly cookie implicitly sent by the browser to authorize and 
    rotate tokens without exposing lifecycle operations to frontend script context.
    """
    def post(self, request, *args, **kwargs):
        # Extract cookie data and inject it manually into the active request data payload
        cookie_name = JWT_SETTINGS.get('AUTH_COOKIE', 'refresh_token')
        refresh_token = request.COOKIES.get(cookie_name)
        
        if refresh_token:
            if hasattr(request.data, '_mutable'):
                request.data._mutable = True
            request.data['refresh'] = refresh_token
            
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            new_refresh = response.data.get('refresh')
            # If token rotation is enabled, silently update the dropped browser cookie
            if new_refresh:
                # Address dynamic secure cookie flag to prevent browser drop in local HTTP dev
                secure_cookie = JWT_SETTINGS.get('AUTH_COOKIE_SECURE', False) and request.is_secure()
                
                response.set_cookie(
                    key=cookie_name,
                    value=new_refresh,
                    expires=JWT_SETTINGS.get('REFRESH_TOKEN_LIFETIME'),
                    secure=secure_cookie,
                    httponly=JWT_SETTINGS.get('AUTH_COOKIE_HTTP_ONLY', True),
                    path=JWT_SETTINGS.get('AUTH_COOKIE_PATH', '/api/auth/'),
                    samesite=JWT_SETTINGS.get('AUTH_COOKIE_SAMESITE', 'Lax')
                )
                # Keep JSON response completely clean of the raw refresh data
                del response.data['refresh']
        return response


class LogoutAPIView(APIView):
    """
    Production logout view that safely pulls the refresh token out of the cookie context, 
    adds it to the backend outstanding token blacklist, and deletes the browser cookie.
    """
    permission_classes = [AllowAny]  # Allows checking even if access token is already dead

    def post(self, request):
        try:
            cookie_name = JWT_SETTINGS.get('AUTH_COOKIE', 'refresh_token')
            refresh_token = request.COOKIES.get(cookie_name)
            
            if refresh_token:
                # Blacklist token immediately in the database
                token = RefreshToken(refresh_token)
                token.blacklist()
                
            # Log the user out of the Django session context
            logout(request)
            
            response = Response({"message": "Session destroyed successfully."}, status=status.HTTP_200_OK)
            
            # Obliterate the authentication cookie out of the browser client environment
            response.delete_cookie(
                key=cookie_name,
                path=JWT_SETTINGS.get('AUTH_COOKIE_PATH', '/api/auth/')
            )
            return response
        except Exception:
            return Response({"error": "Invalid session profile configuration."}, status=status.HTTP_400_BAD_REQUEST)
        
class EmailOrUsernameModelBackend(ModelBackend):
    """Authenticates users via either exact email or exact username string."""
    def authenticate(self, request, username=None, password=None, **kwargs):
        # 1. Fallback: if username is None, grab the value from kwargs (like email=...)
        login_val = username or kwargs.get('email') or kwargs.get('username')
        
        if not login_val:
            return None
            
        from django.contrib.auth import get_user_model
        User = get_user_model()
            
        try:
            # 2. Look up the identifier string against both columns case-insensitively
            user = User.objects.get(Q(email__iexact=login_val) | Q(username__iexact=login_val))
        except User.DoesNotExist:
            return None

        # 3. Check password validity
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
    
def verify_email_view(request, token):
    """
    Validates the cryptographically signed token sent to the user's email.
    If valid and active, completes email confirmation.
    """
    try:
        # Decrypt token, verifying it hasn't been tampered with or expired
        user_id = signer.unsign(token, max_age=TOKEN_MAX_AGE)
        User = get_user_model()
        user = User.objects.get(pk=user_id)
        
        # Query Profile directly using the user instance to satisfy Pylance
        profile = Profile.objects.get(user=user)
        
        if not profile.is_email_verified:
            profile.is_email_verified = True
            profile.save()
            messages.success(request, "Your email address has been verified! Log in to complete onboarding.")
        else:
            messages.info(request, "This account's email has already been verified.")
            
        return redirect('login_page') # Redirects straight to your login template view
        
    except SignatureExpired:
        messages.error(request, "Your verification link has expired. Please sign up again to generate a new link.")
        return render(request, 'registration/verification_failed.html')
    except (BadSignature, User.DoesNotExist, Profile.DoesNotExist): # default catch-all for invalid or tampered tokens
        messages.error(request, "The verification link is invalid or corrupted.")
        return render(request, 'registration/verification_failed.html')