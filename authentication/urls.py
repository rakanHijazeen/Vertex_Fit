from django.urls import path
from .views import LogoutAPIView, RegistrationAPIView, ProfileUpdateAPIView, LoginAPIView, login_page, signup_page

app_name = 'authentication'

urlpatterns = [
    # Template Pages
    path('login/', login_page, name='login'),
    path('signup/', signup_page, name='signup'),

    # DRF API Endpoints
    path('register/phase-1/', RegistrationAPIView.as_view(), name='register-phase-1'),
    path('register/phase-2/', ProfileUpdateAPIView.as_view(), name='register-phase-2'),
    path('api/login/', LoginAPIView.as_view(), name='api_login'),
    path('api/logout/', LogoutAPIView.as_view(), name='api_logout'),
]