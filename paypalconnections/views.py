import zlib
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
import requests
import json
import hmac
import hashlib
from paypalconnections.paypal_utils import get_paypal_access_token
from signup.models import CustomUser
from .models import PayPalAccount

class ConnectPayPalView(APIView):
    """Initiate PayPal seller onboarding using the Partner Referrals API"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Store user ID in session to retrieve in callback
        request.session['connecting_user_id'] = request.user.id

        # Get PayPal access token
        try:
            access_token = get_paypal_access_token()
        except Exception as e:
            return Response({"error": "Failed to get access token", "details": str(e)}, status=400)

        # Define the return URL (must be publicly accessible)
        return_url = "https://airedale-destined-antelope.ngrok-free.app/api/paypal-onboarding-callback/"

        # Prepare the Partner Referrals API request
        url = "https://api-m.sandbox.paypal.com/v2/customer/partner-referrals"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        data = {
            "products": ["EXPRESS_CHECKOUT"],  # Use PPCP for advanced features like Expanded Checkout
            "partner_config_override": {
                "return_url": return_url,
                "return_url_description": "Return to the platform after onboarding",
            },
            "operations": [
                {
                    "operation": "API_INTEGRATION",
                    "api_integration_preference": {
                        "rest_api_integration": {
                            "integration_method": "PAYPAL",
                            "integration_type": "THIRD_PARTY",
                            "third_party_details": {
                                "features": ["PAYMENT", "REFUND"]
                            }
                        }
                    }
                }
            ],
            # Pre-fill seller data (optional)
            "business_entity": {
                "email": request.user.email,
            },
            # Tracking ID to monitor onboarding status
            "tracking_id": f"seller-{request.user.id}",
        }

        # Make the API call to generate the sign-up link
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            response_data = response.json()
            # Extract the action_url from the response links
            action_url = next(
                link["href"] for link in response_data["links"] if link["rel"] == "action_url"
            )
            return Response({"action_url": action_url})
        except Exception as e:
            return Response({"error": "Failed to initiate PayPal onboarding", "details": str(e)}, status=400)
    

class PayPalOnboardingCallbackView(APIView):
    """Handle the callback from PayPal after seller onboarding"""
    permission_classes = [AllowAny]

    def get(self, request):
        # Extract query parameters
        auth_code = request.query_params.get("authCode")
        shared_id = request.query_params.get("sharedId")
        seller_merchant_id = request.query_params.get("merchantIdInPayPal")

        if not all([auth_code, shared_id, seller_merchant_id]):
            return Response({"error": "Missing required query parameters"}, status=400)

        # Retrieve user ID from session
        user_id = request.session.get('connecting_user_id')
        if not user_id:
            return Response({"error": "User session not found"}, status=400)

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=400)

        # Get PayPal access token (your platform's token)
        try:
            access_token = get_paypal_access_token()
        except Exception as e:
            return Response({"error": "Failed to get access token", "details": str(e)}, status=400)

        # Exchange authCode for seller's access token
        url = "https://api-m.sandbox.paypal.com/v1/oauth2/token"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "shared_id": shared_id,
        }
        try:
            response = requests.post(url, headers=headers, data=data)
            response.raise_for_status()
            token_data = response.json()
            seller_access_token = token_data["access_token"]
        except Exception as e:
            return Response({"error": "Failed to get seller access token", "details": str(e)}, status=400)

        # Get seller's REST API credentials
        url = f"https://api-m.sandbox.paypal.com/v1/customer/partners/{settings.PAYPAL_PARTNER_MERCHANT_ID}/merchant-integrations/credentials/"
        headers = {
            "Authorization": f"Bearer {seller_access_token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            credentials = response.json()
            seller_client_id = credentials["client_id"]
            seller_client_secret = credentials["client_secret"]
        except Exception as e:
            return Response({"error": "Failed to get seller credentials", "details": str(e)}, status=400)

        # Save the seller's credentials and details to your database
        try:
            PayPalAccount.objects.update_or_create(
                user=user,
                defaults={
                    "paypal_email": user.email,  # Update if you fetch email from PayPal
                    "account_id": seller_merchant_id,
                    "access_token": seller_access_token,
                    "client_id": seller_client_id,
                    "client_secret": seller_client_secret,
                    "is_active": True,
                }
            )
        except Exception as e:
            return Response({"error": "Failed to save PayPal account", "details": str(e)}, status=400)

        # Clear the session variable
        request.session.pop('connecting_user_id', None)

        # Redirect to frontend
        return redirect(settings.FRONTEND_URL + "/account/payment-methods?connected=true")

class PayPalStatusView(APIView):
    """Get the status of the user's PayPal connection"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            paypal_account = PayPalAccount.objects.get(user=request.user, is_active=True)
            return Response({
                "connected": True,
                "paypal_email": paypal_account.paypal_email,
                "account_id": paypal_account.account_id,
                "token_valid": paypal_account.token_valid
            })
        except PayPalAccount.DoesNotExist:
            return Response({"connected": False})


class DisconnectPayPalView(APIView):
    """Disconnect the user's PayPal account"""
    permission_classes = [IsAuthenticated]
    
    def delete(self, request):
        try:
            paypal_account = PayPalAccount.objects.get(user=request.user)
            paypal_account.is_active = False
            paypal_account.save()
            return Response({"message": "PayPal account disconnected successfully"})
        except PayPalAccount.DoesNotExist:
            return Response({"error": "No PayPal account connected"}, status=status.HTTP_404_NOT_FOUND)
        

class PayPalWebhookView(APIView):
    """Handle PayPal webhook events"""
    permission_classes = [AllowAny]

    def post(self, request):
        # Extract headers for verification
        transmission_id = request.headers.get("Paypal-Transmission-Id")
        timestamp = request.headers.get("Paypal-Transmission-Time")
        webhook_id = request.headers.get("Paypal-Webhook-Id")
        crc32_signature = request.headers.get("Paypal-Transmission-Sig")
        event_type = request.headers.get("Paypal-Event-Type")

        if not all([transmission_id, timestamp, webhook_id, crc32_signature, event_type]):
            return Response({"error": "Missing required headers"}, status=status.HTTP_400_BAD_REQUEST)

        # Verify the webhook signature
        raw_body = request.body.decode("utf-8")
        expected_signature = f"{transmission_id}|{timestamp}|{webhook_id}|{crc32(str(raw_body))}"
        computed_signature = hmac.new(
            settings.PAYPAL_WEBHOOK_SECRET.encode("utf-8"),
            expected_signature.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_signature, crc32_signature):
            return Response({"error": "Invalid webhook signature"}, status=status.HTTP_400_BAD_REQUEST)

        # Parse the webhook event
        try:
            event = json.loads(raw_body)
        except json.JSONDecodeError:
            return Response({"error": "Invalid JSON payload"}, status=status.HTTP_400_BAD_REQUEST)

        # Process the event based on event_type
        if event_type == "MERCHANT.ONBOARDING.COMPLETED":
            # Extract tracking_id to identify the seller
            tracking_id = event.get("resource", {}).get("tracking_id")
            if tracking_id and tracking_id.startswith("seller-"):
                user_id = tracking_id.split("-")[1]
                try:
                    user = CustomUser.objects.get(id=user_id)
                    paypal_account = PayPalAccount.objects.get(user=user)
                    paypal_account.is_active = True  # Mark as fully onboarded
                    paypal_account.save()
                except (CustomUser.DoesNotExist, PayPalAccount.DoesNotExist):
                    pass  # Log this error in production
        elif event_type == "MERCHANT.PARTNER-CONSENT.REVOKED":
            # Handle permission revocation
            merchant_id = event.get("resource", {}).get("merchant_id")
            try:
                paypal_account = PayPalAccount.objects.get(account_id=merchant_id)
                paypal_account.is_active = False  # Deactivate the account
                paypal_account.save()
            except PayPalAccount.DoesNotExist:
                pass  # Log this error in production

        # Acknowledge the webhook event
        return Response({"status": "success"}, status=status.HTTP_200_OK)

def crc32(data):
    """Compute CRC32 hash for webhook verification"""
    return format(zlib.crc32(data.encode("utf-8")) & 0xFFFFFFFF, "08x")