import json
import os
import requests
from django.shortcuts import render
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
from paddle_billing.Notifications import Secret, Verifier
from .models import UserSubscription, PlanTier, BillingCycle

User = get_user_model()

def pricing_page(request):
    context = {
        'PADDLE_CLIENT_TOKEN': os.getenv('PADDLE_CLIENT_TOKEN', ''),
        'PADDLE_PRO_PRICE_ID': os.getenv('PADDLE_PRO_PRICE_ID', ''), # 5 JOD / mo
        'PADDLE_ANNUAL_PRICE_ID': os.getenv('PADDLE_ANNUAL_PRICE_ID', ''), # 45 JOD / yr
        'PADDLE_VIP_PRICE_ID': os.getenv('PADDLE_VIP_PRICE_ID', ''), # 10 JOD / mo
    }
    return render(request, 'payments/pricing.html', context)

def success_page(request):
    return render(request, 'payments/success.html')

# Subscription Status API View
class SubscriptionStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub = getattr(request.user, 'subscription', None)
        if not sub:
            return Response({"error": "No subscription found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "tier": sub.tier,
            "status": sub.status,
            "billing_cycle": sub.billing_cycle,
            "live_coach_seconds_remaining": sub.live_coach_seconds_remaining,
            "can_upload_retroactive_video": sub.can_upload_retroactive_video,
        }, status=status.HTTP_200_OK)

class CreateCheckoutSessionAPIView(APIView):
    """
    Creates a Paddle server-side transaction for the authenticated user 
    and returns the transaction ID to launch Paddle.js on the frontend.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        price_id = request.data.get("price_id")
        if not price_id:
            return Response({"error": "price_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        sub, _ = UserSubscription.objects.get_or_create(user=user)

        # 1. Prepare Paddle API Request Payload
        paddle_api_key = os.getenv("PADDLE_API_KEY")
        paddle_env = os.getenv("PADDLE_ENVIRONMENT", "sandbox")
        
        base_url = "https://sandbox-api.paddle.com" if paddle_env == "sandbox" else "https://api.paddle.com"

        headers = {
            "Authorization": f"Bearer {paddle_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "items": [{"price_id": price_id, "quantity": 1}],
            "custom_data": {
                "user_id": user.id  # Critical for mapping webhook back to Django User
            }
        }

        # If user already has a Paddle customer ID, attach it
        if sub.paddle_customer_id:
            payload["customer_id"] = sub.paddle_customer_id

        # 2. Request Transaction creation from Paddle API
        try:
            response = requests.post(f"{base_url}/transactions", json=payload, headers=headers)
            res_data = response.json()

            if response.status_code in [200, 201]:
                transaction_id = res_data["data"]["id"]
                return Response({
                    "transaction_id": transaction_id
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Failed to create checkout transaction", "details": res_data}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        
def get_paddle_price_map():
    """
    Maps Paddle price IDs to their corresponding PlanTier and BillingCycle.
    """
    price_map = {}
    
    pro_price = os.getenv("PADDLE_PRO_PRICE_ID")
    if pro_price:
        price_map[pro_price] = (PlanTier.PRO, BillingCycle.MONTHLY)

    vip_price = os.getenv("PADDLE_VIP_PRICE_ID")
    if vip_price:
        price_map[vip_price] = (PlanTier.VIP, BillingCycle.MONTHLY)

    annual_price = os.getenv("PADDLE_ANNUAL_PRICE_ID")
    if annual_price:
        price_map[annual_price] = (PlanTier.PRO, BillingCycle.YEARLY)

    return price_map


@csrf_exempt
def paddle_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    webhook_secret_str = os.getenv("PADDLE_WEBHOOK_SECRET")
    if not webhook_secret_str:
        return JsonResponse({"error": "Webhook secret unconfigured"}, status=500)

    # 1. Signature Verification
    webhook_secret = Secret(webhook_secret_str)
    if not Verifier().verify(request, webhook_secret):
        return JsonResponse({"error": "Invalid signature"}, status=400)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    event_type = payload.get("event_type")
    data = payload.get("data", {})

    # 2. Event Dispatching
    if event_type in ["subscription.created", "subscription.updated", "transaction.completed"]:
        handle_subscription_sync(data)
    elif event_type in ["subscription.canceled", "subscription.past_due"]:
        handle_subscription_canceled(data)

    return JsonResponse({"status": "ok"}, status=200)


def handle_subscription_sync(data):
    """Handles active subscriptions, tier updates, and new checkouts."""
    custom_data = data.get("custom_data") or {}
    user_id = custom_data.get("user_id")
    
    sub_id = data.get("id") or data.get("subscription_id")
    customer_id = data.get("customer_id")
    status = data.get("status", "active") # e.g. 'active', 'trialing'
    
    # Extract Price ID from line items
    items = data.get("items", [])
    price_id = items[0]["price"]["id"] if items and "price" in items[0] else None
    
    # Map Price ID to Tier & Billing Cycle using .env lookup
    price_map = get_paddle_price_map()
    tier, billing_cycle = price_map.get(
        price_id, 
        (PlanTier.FREE, BillingCycle.MONTHLY)
    )

    if user_id:
        user = User.objects.filter(id=user_id).first()
        if user:
            sub, _ = UserSubscription.objects.get_or_create(user=user)
            sub.paddle_subscription_id = sub_id
            sub.paddle_customer_id = customer_id
            sub.price_id = price_id
            sub.status = status
            sub.tier = tier if status in ["active", "trialing"] else PlanTier.FREE
            sub.billing_cycle = billing_cycle
            sub.save()


def handle_subscription_canceled(data):
    """Handles canceled or failed subscriptions and downgrades the user to Free."""
    sub_id = data.get("id")
    if not sub_id:
        return

    sub = UserSubscription.objects.filter(paddle_subscription_id=sub_id).first()
    if sub:
        sub.status = data.get("status", "canceled")
        sub.tier = PlanTier.FREE
        sub.save()