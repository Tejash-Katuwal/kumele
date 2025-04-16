import base64
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
from .models import PayPalAccount, PayPalTransaction

class ConnectPayPalView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Get platform from query parameters
        platform = request.query_params.get('platform', 'web')
        user_id = request.user.id
        
        # Store user ID in session for web only
        if platform == 'web':
            request.session['connecting_user_id'] = user_id
            return_url = "http://127.0.0.1:8000/api/paypal-onboarding-callback/?platform=web"
        elif platform == 'ios':
            # For iOS, use a deep link URL scheme
            return_url = f"kumele://paypal-callback?user_id={user_id}&platform=ios"
        elif platform == 'android':
            # For Android, use a deep link URL scheme
            return_url = f"kumele://paypal-callback?user_id={user_id}&platform=android"
        else:
            return Response({"error": "Invalid platform"}, status=400)

        # Get platform's access token (using client ID and secret)
        try:
            access_token = get_paypal_access_token()
        except Exception as e:
            return Response({"error": "Failed to connect to PayPal", "details": str(e)}, status=400)

        # Prepare the request to PayPal's Partner Referrals API
        url = "https://api-m.sandbox.paypal.com/v2/customer/partner-referrals"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        data = {
            "products": ["EXPRESS_CHECKOUT"],  # Basic PayPal checkout
            "partner_config_override": {
                "return_url": return_url,
                "return_url_description": "Return to our platform",
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
            "legal_consents": [
                {
                    "type": "SHARE_DATA_CONSENT",
                    "granted": True
                }
            ],
            "business_entity": {
                "email": request.user.email,  # Pre-fill seller's email
            },
            "tracking_id": f"seller-{request.user.id}-{platform}",  # Include platform in tracking ID
        }

        # Send the request to PayPal
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            response_data = response.json()

            # Find the sign-up URL in PayPal's response
            action_url = next(
                link["href"] for link in response_data["links"] if link["rel"] == "action_url"
            )
            return Response({
                "action_url": action_url,
                "platform": platform
            })
        except Exception as e:
            return Response({"error": "Failed to start onboarding", "details": str(e)}, status=400)
    

class PayPalOnboardingCallbackView(APIView):
    """Handle the callback from PayPal after seller onboarding"""
    permission_classes = [AllowAny]

    def get(self, request):
        # Extract query parameters

        print("The endpoint has reached here above extracting query parameters!!!!\n")

        seller_merchant_id = request.query_params.get("merchantIdInPayPal")
        permissions_granted = request.query_params.get("permissionsGranted") == "true"
        consent_status = request.query_params.get("consentStatus") == "true"
        merchant_id = request.query_params.get("merchantId")
        platform = request.query_params.get("platform", "web")


        print("merchant ID: ", merchant_id)

        
        # Check for required parameters
        if not seller_merchant_id:
            return Response({"error": "Missing merchantIdInPayPal parameter"}, status=400)
            
        # Verify permissions and consent
        if not (permissions_granted and consent_status):
            return Response({"error": "Permissions or consent not granted"}, status=400)
        
        print("\nThe endpoint has reached here!!!!")

        # Extract user ID from merchantId parameter if available
        user_id = None
        if merchant_id and merchant_id.startswith("seller-"):
            try:
                user_id = int(merchant_id.split("-")[1])
            except (IndexError, ValueError):
                pass

                
        # If still not found, try session as fallback (for web)
        if not user_id and platform == "web":
            user_id = request.session.get('connecting_user_id')
            
        if not user_id:
            return Response({"error": "User identification not found"}, status=400)

        try:
            user = CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=400)
        try:
            PayPalAccount.objects.update_or_create(
                user=user,
                defaults={
                    "paypal_email": user.email,
                    "account_id": seller_merchant_id,
                    "is_active": True,
                }
            )
        except Exception as e:
            return Response({"error": "Failed to save PayPal account", "details": str(e)}, status=400)

        # Clear session if web
        if platform == "web":
            request.session.pop('connecting_user_id', None)
            return redirect(settings.FRONTEND_URL + "/account/payment-methods?connected=true")
        else:
            # For mobile, just return a success response
            return Response({
                "success": True,
                "connected": True,
                "paypal_email": user.email,
                "account_id": seller_merchant_id,
            })
    

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
    permission_classes = [AllowAny]

    def post(self, request):
        # Extract headers
        transmission_id = request.headers.get("Paypal-Transmission-Id")
        timestamp = request.headers.get("Paypal-Transmission-Time")
        webhook_id = request.headers.get("Paypal-Webhook-Id")
        crc32_signature = request.headers.get("Paypal-Transmission-Sig")
        event_type = request.data.get("event_type")

        if not all([transmission_id, timestamp, webhook_id, crc32_signature]):
            return Response({"error": "Missing headers"}, status=400)

        # Verify signature
        raw_body = request.body.decode("utf-8")
        expected_signature = f"{transmission_id}|{timestamp}|{webhook_id}|{zlib.crc32(raw_body.encode('utf-8')) & 0xFFFFFFFF}"
        computed_signature = hmac.new(
            settings.PAYPAL_WEBHOOK_SECRET.encode("utf-8"),
            expected_signature.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_signature, crc32_signature):
            return Response({"error": "Invalid signature"}, status=400)

        # Process event
        if event_type == "MERCHANT.ONBOARDING.COMPLETED":
            tracking_id = request.data.get("resource", {}).get("tracking_id")
            merchant_id = request.data.get("resource", {}).get("merchant_id")
            if tracking_id and tracking_id.startswith("seller-"):
                try:
                    user_id = tracking_id.split("-")[1]
                    user = CustomUser.objects.get(id=user_id)
                    paypal_account = PayPalAccount.objects.get(user=user)
                    paypal_account.account_id = merchant_id
                    paypal_account.is_active = True
                    paypal_account.save()
                except (CustomUser.DoesNotExist, PayPalAccount.DoesNotExist):
                    print(f"Webhook: Could not find user or account for tracking_id {tracking_id}")

        elif event_type == "CHECKOUT.ORDER.COMPLETED":
            order_id = request.data.get("resource", {}).get("id")
            merchant_id = request.data.get("resource", {}).get("purchase_units", [{}])[0].get("payee", {}).get("merchant_id")
            try:
                paypal_account = PayPalAccount.objects.get(account_id=merchant_id)
                transaction = PayPalTransaction.objects.get(transaction_id=order_id)
                transaction.status = "completed"
                transaction.save()
            except (PayPalAccount.DoesNotExist, PayPalTransaction.DoesNotExist):
                print(f"Webhook: Could not process order {order_id}")

        return Response({"status": "success"})

def crc32(data):
    """Compute CRC32 hash for webhook verification"""
    return format(zlib.crc32(data.encode("utf-8")) & 0xFFFFFFFF, "08x")