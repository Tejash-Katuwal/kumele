import pyotp
import qrcode
from io import BytesIO
import base64
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from signup.models import CustomUser
from .models import TwoFactorAuth
from .serializers import TwoFactorEnableSerializer, TwoFactorStatusSerializer
from hobbies.serializers import HobbySerializer
from rest_framework.authtoken.models import Token


class TwoFactorSetupView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Generate a new 2FA secret and return setup information"""
        user = request.user
        
        # Generate a new secret key
        secret = pyotp.random_base32()
        
        # Store the secret temporarily in the session
        request.session['2fa_temp_secret'] = secret
        
        # Create a TOTP object
        totp = pyotp.TOTP(secret)
        
        # Create a QR code URI for scanning with authenticator apps
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name="Kumele"
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        
        # Convert QR code to base64 for embedding in response
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        qr_image_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return Response({
            'secret': secret,
            'qr_code': f"data:image/png;base64,{qr_image_base64}",
            'message': 'Scan this QR code with your authenticator app, then verify with a code to enable 2FA.'
        }, status=status.HTTP_200_OK)


class TwoFactorEnableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Enable 2FA after verification"""
        user = request.user
        serializer = TwoFactorEnableSerializer(data=request.data)
        
        if serializer.is_valid():
            # Get the temporary secret from the session
            secret = request.session.get('2fa_temp_secret')
            if not secret:
                return Response({"error": "2FA setup not initiated"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Verify the provided code
            totp = pyotp.TOTP(secret)
            if totp.verify(serializer.validated_data['verification_code']):
                # Generate backup codes
                backup_codes = [pyotp.random_base32()[:8] for _ in range(5)]
                
                # Save 2FA data
                two_factor, created = TwoFactorAuth.objects.get_or_create(
                    user=user,
                    defaults={
                        'secret_key': secret,
                        'backup_codes': backup_codes
                    }
                )
                
                if not created:
                    # Update if already exists
                    two_factor.secret_key = secret
                    two_factor.backup_codes = backup_codes
                    two_factor.save()
                
                # Enable 2FA on user profile
                user.two_factor_enabled = True
                user.save()
                
                # Clear the temporary secret
                if '2fa_temp_secret' in request.session:
                    del request.session['2fa_temp_secret']
                
                return Response({
                    "message": "Two-factor authentication enabled successfully",
                    "backup_codes": backup_codes,
                    "important": "Save these backup codes safely. They will be needed if you lose access to your authenticator app."
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class TwoFactorDisableView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Disable 2FA after verification"""
        user = request.user
        
        if not user.two_factor_enabled:
            return Response({"message": "Two-factor authentication is already disabled"}, 
                           status=status.HTTP_200_OK)
        
        # Get the verification code from request
        verification_code = request.data.get('verification_code')
        if not verification_code:
            return Response({"error": "Verification code is required"}, 
                           status=status.HTTP_400_BAD_REQUEST)
        
        try:
            two_factor = TwoFactorAuth.objects.get(user=user)
            
            # Verify the provided code
            totp = pyotp.TOTP(two_factor.secret_key)
            
            # Check if it's a valid TOTP code
            if totp.verify(verification_code):
                # Disable 2FA
                user.two_factor_enabled = False
                user.save()
                return Response({"message": "Two-factor authentication disabled successfully"}, 
                               status=status.HTTP_200_OK)
            
            # Check if it's a valid backup code
            elif verification_code in two_factor.backup_codes:
                # Disable 2FA
                user.two_factor_enabled = False
                user.save()
                return Response({"message": "Two-factor authentication disabled successfully using backup code"}, 
                               status=status.HTTP_200_OK)
            
            else:
                return Response({"error": "Invalid verification code"}, 
                               status=status.HTTP_400_BAD_REQUEST)
                
        except TwoFactorAuth.DoesNotExist:
            return Response({"error": "Two-factor authentication data not found"}, 
                           status=status.HTTP_400_BAD_REQUEST)

class TwoFactorStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Check if 2FA is enabled"""
        serializer = TwoFactorStatusSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class TwoFactorVerifyView(APIView):
    """
    Endpoint to verify a 2FA code during login process
    This would be called after successful username/password authentication
    """
    def post(self, request):
        email = request.data.get('email')
        verification_code = request.data.get('verification_code')
        
        if not email or not verification_code:
            return Response({"error": "Email and verification code are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = CustomUser.objects.get(email=email)
            
            if not user.two_factor_enabled:
                return Response({"error": "Two-factor authentication is not enabled for this user"}, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                two_factor = TwoFactorAuth.objects.get(user=user)
                token, _ = Token.objects.get_or_create(user=user)
                
                # Check if the code is a valid TOTP code
                totp = pyotp.TOTP(two_factor.secret_key)
                if totp.verify(verification_code):
                    # Update last used time
                    two_factor.last_used_at = timezone.now()
                    two_factor.save()
                    
                    return Response({"message": "Two-factor authentication successful",
                                    "referral_code": user.referral_code,
                                    "name": user.name,
                                    "email": user.email,
                                    'username': user.username or '',
                                    "dob": user.date_of_birth.isoformat() if user.date_of_birth else '',
                                    "gender": user.gender,
                                    "picture_url": user.get_picture_url() or '',
                                    "user_token": token.key,
                                    "above_legal_age": user.above_legal_age,
                                    "terms_and_conditions": user.terms_and_conditions,
                                    "hobbies": HobbySerializer(user.hobbies.all(), many=True).data,
                                    "next_step": "welcome" if user.hobbies.exists() else "hobbies",
                                    "qr_code_url": user.qr_code_url or '',
                                    "sound_notification": user.sound_notifications,
                                    "email_notification": user.email_notifications,
                                }, status=status.HTTP_200_OK)
                
                # Check if the code is a valid backup code
                elif verification_code in two_factor.backup_codes:
                    # Remove the used backup code
                    backup_codes = two_factor.backup_codes
                    backup_codes.remove(verification_code)
                    two_factor.backup_codes = backup_codes
                    two_factor.last_used_at = timezone.now()
                    two_factor.save()
                    
                    return Response({
                        "message": "Two-factor authentication successful using backup code",
                        "referral_code": user.referral_code,
                        "name": user.name,
                        "email": user.email,
                        'username': user.username or '',
                        "dob": user.date_of_birth.isoformat() if user.date_of_birth else '',
                        "gender": user.gender,
                        "picture_url": user.get_picture_url() or '',
                        "user_token": token.key,
                        "above_legal_age": user.above_legal_age,
                        "terms_and_conditions": user.terms_and_conditions,
                        "hobbies": HobbySerializer(user.hobbies.all(), many=True).data,
                        "next_step": "welcome" if user.hobbies.exists() else "hobbies",
                        "qr_code_url": user.qr_code_url or '',
                        "sound_notification": user.sound_notifications,
                        "email_notification": user.email_notifications,
                        "warning": "You've used a backup code. Only {} backup codes remaining.".format(len(backup_codes))
                    }, status=status.HTTP_200_OK)
                
                else:
                    return Response({"error": "Invalid verification code"}, status=status.HTTP_400_BAD_REQUEST)
            
            except TwoFactorAuth.DoesNotExist:
                return Response({"error": "Two-factor authentication data not found"}, status=status.HTTP_400_BAD_REQUEST)
        
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)