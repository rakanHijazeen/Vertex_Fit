from django.urls import path
from .views import LogoutAPIView, RegistrationAPIView, LoginAPIView, login_page, signup_page

app_name = 'authentication'

urlpatterns = [
    # Template Pages
    path('login/', login_page, name='login'),
    path('signup/', signup_page, name='signup'),

    # DRF API Endpoints
    path('api/register/', RegistrationAPIView.as_view(), name='api_register'),
    path('api/login/', LoginAPIView.as_view(), name='api_login'),
    path('api/logout/', LogoutAPIView.as_view(), name='api_logout'),
]