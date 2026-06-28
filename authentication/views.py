from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegistrationSerializer

class RegistrationAPIView(APIView):
    """Handles secure atomic user registration and immediate JWT token provision."""
    permission_classes = [AllowAny]  # Let anyone access registration

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
            # Programmatically generate JWT token tokens for the newly registered user
            refresh = RefreshToken.for_user(user)
            
            return Response({
                "message": "User and profile registered successfully.",
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                }
            }, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)