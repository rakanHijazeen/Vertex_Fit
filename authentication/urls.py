from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
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
    # Email Verification Callback
    path('verify-email/<str:token>/', views.verify_email_view, name='verify_email'),

    # Password Reset Loop (Using built-in Class Views which trigger our custom Brevo backend)
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/emails/password_reset_email.html',
             subject_template_name='registration/emails/password_reset_subject.txt'
         ), 
         name='password_reset'),
    
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), 
         name='password_reset_done'),
    
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), 
         name='password_reset_confirm'),
         
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), 
         name='password_reset_complete'),
]