"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from authentication.views import (
    RegistrationAPIView, ProfileUpdateAPIView,  login_page, LogoutAPIView, signup_page, onboarding_page,
    LoginAPIView, ProductionTokenRefreshAPIView, verify_email_view, landing_page, profile_page, ProfileSettingsAPIView
)

urlpatterns = [
    # Auto-Redirect empty root URL to the web interface login template
    path('', RedirectView.as_view(url='auth/login/', permanent=False), name='root_redirect'),
    path('admin/', admin.site.urls),

    # Point directly to the explicit landing view
    path('', landing_page, name='landing'),

    # Django-Allauth URLs for social authentication (Google, etc.)
    path('accounts/', include('allauth.urls')),
    
    # Auth Views
    path('auth/login/', login_page, name='login_page'),
    path('auth/signup/', signup_page, name='signup_page'),
    path('auth/onboarding/', onboarding_page, name='onboarding_page'), # 2. Serves the onboarding.html page
    path('auth/profile/', profile_page, name='profile_page'),
    
    # Email Verification Route clicked by the user from their inbox
    path('auth/verify-email/<str:token>/', verify_email_view, name='verify_email'),

    # Connect the Workouts App routing (Handles both API endpoints and the HTML Tracker)
    path('api/workouts/', include('workouts.urls')),

    # Backend Authentication Engine Endpoints
    path('api/auth/register/phase-1/', RegistrationAPIView.as_view(), name='auth_register_phase_1'), # 3. Replaced old endpoint
    path('api/auth/register/phase-2/', ProfileUpdateAPIView.as_view(), name='auth_register_phase_2'), # 4. Added phase 2 PATCH endpoint
    path('api/auth/login/', LoginAPIView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', ProductionTokenRefreshAPIView.as_view(), name='token_refresh'),  
    path('api/auth/logout/', LogoutAPIView.as_view(), name='token_blacklist'), 
    path('api/profile/update/', ProfileSettingsAPIView.as_view(), name='profile_update'),

    # Internal API routing for the Authentication App (Handles both API endpoints and the HTML login/signup pages)
    path('api/auth-core/', include('authentication.urls', namespace='authentication')),

    # DJANGO CORE PASSWORD RESET WITH EXPLICIT HTML EMAIL DISPATCH
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='authentication/password_reset_form.html',
             # This sends the clean text version for strict mail clients:
             email_template_name='authentication/emails/password_reset_subject.txt', 
             # This forces Django to compile and send the beautiful HTML version! 👇
             html_email_template_name='authentication/emails/password_reset_email.html',
             subject_template_name='authentication/emails/password_reset_subject.txt',
             success_url='/password-reset/done/'
         ), 
         name='password_reset'),
         
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='authentication/password_reset_done.html'
         ), 
         name='password_reset_done'),
         
    path('password-reset/confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='authentication/password_reset_confirm.html',
             success_url='/password-reset/complete/'
         ), 
         name='password_reset_confirm'),
         
    path('password-reset/complete/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='authentication/password_reset_complete.html'
         ), 
         name='password_reset_complete'),
        
]


# Append local media file serving context logic
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)