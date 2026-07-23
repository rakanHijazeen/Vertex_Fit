from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    # Template Views
    path('pricing/', views.pricing_page, name='pricing'),
    path('success/', views.success_page, name='success'),

    # API / Webhook Endpoints
    path('api/subscription/status/', views.SubscriptionStatusAPIView.as_view(), name='subscription_status'),
    path('api/paddle/webhook/', views.paddle_webhook, name='paddle_webhook'),
    path('api/checkout/session/', views.CreateCheckoutSessionAPIView.as_view(), name='checkout_session'),
]