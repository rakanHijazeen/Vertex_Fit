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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from authentication.views import (
    RegistrationAPIView, ProfileUpdateAPIView,  login_page, LogoutAPIView, signup_page, onboarding_page,
    LoginAPIView, ProductionTokenRefreshAPIView
)

urlpatterns = [
    # Auto-Redirect empty root URL to the web interface login template
    path('', RedirectView.as_view(url='auth/login/', permanent=False), name='root_redirect'),
    path('admin/', admin.site.urls),

    # Auth Views
    path('auth/login/', login_page, name='login_page'),
    path('auth/signup/', signup_page, name='signup_page'),
    path('auth/onboarding/', onboarding_page, name='onboarding_page'), # 2. Serves the onboarding.html page
    
    # Connect the Workouts App routing (Handles both API endpoints and the HTML Tracker)
    path('api/workouts/', include('workouts.urls')),

    # Backend Authentication Engine Endpoints
    path('api/auth/register/phase-1/', RegistrationAPIView.as_view(), name='auth_register_phase_1'), # 3. Replaced old endpoint
    path('api/auth/register/phase-2/', ProfileUpdateAPIView.as_view(), name='auth_register_phase_2'), # 4. Added phase 2 PATCH endpoint
    path('api/auth/login/', LoginAPIView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', ProductionTokenRefreshAPIView.as_view(), name='token_refresh'),  
    path('api/auth/logout/', LogoutAPIView.as_view(), name='token_blacklist'), 

    # Internal API routing for the Authentication App (Handles both API endpoints and the HTML login/signup pages)
    path('api/auth-core/', include('authentication.urls', namespace='authentication')),

        
]


# Append local media file serving context logic
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)