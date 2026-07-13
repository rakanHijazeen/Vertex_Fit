from rest_framework import settings, status
from django.shortcuts import render
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .serializers import Phase1RegistrationSerializer, ProfileUpdateSerializer
from django.contrib.auth import login, logout, get_user_model
from .models import Profile

def login_page(request):
    """Renders the login page template for the web interface."""
    return render(request, 'authentication/login.html')

def signup_page(request):
    """Renders the signup page template for the web interface."""
    return render(request, 'authentication/signup.html')

def onboarding_page(request):
    return render(request, 'authentication/onboarding.html')

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
                user = serializer.save()
                
                # Initialize an incomplete profile stub automatically
                # Stays complete=False until phase 2 data is submitted
                Profile.objects.create(user=user, onboarding_complete=False)
            
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
    Production login endpoint that catches user credentials, returns an access token 
    to client runtime memory, and locks down the refresh token inside an HttpOnly cookie.
    """
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')
            
            # Log the user into Django session context for template page access and WebSocket channels
            User = get_user_model()
            try:
                user = User.objects.get(email=request.data.get('email'))
                login(request, user)
            except User.DoesNotExist:
                pass
            
            # Strip the refresh token out of the JSON response payload to isolate it from XSS surfaces
            response.data = {
                "message": "Authentication successful.",
                "access": access_token
            }
            
            # Address dynamic secure cookie flag to prevent browser drop in local HTTP dev
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