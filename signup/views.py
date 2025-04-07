import base64
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from .models import CustomUser, Referral, PasskeyCredential
from .serializers import (SignupSerializer, 
    VerifyEmailSerializer, 
    GoogleSignInSerializer,
    PermissionsSerializer, 
    SetUsernameSerializer,
    PasskeyRegistrationOptionsSerializer, 
    PasskeyRegistrationVerifySerializer,
    PasskeyLoginOptionsSerializer,
    PasskeyLoginVerifySerializer)
import random
import string
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from rest_framework.authtoken.models import Token
import qrcode
from django.core.files.storage import default_storage
import os
from django.contrib.auth import authenticate
from hobbies.serializers import HobbySerializer
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
)
from webauthn.helpers.exceptions import InvalidRegistrationResponse, InvalidAuthenticationResponse
import secrets
import json
from webauthn.helpers.structs import AuthenticatorSelectionCriteria

def bytes_to_base64url(bytes_data):
        """Convert bytes to base64url encoding without padding"""
        base64_encoded = base64.b64encode(bytes_data).decode('utf-8')
        return base64_encoded.replace('+', '-').replace('/', '_').rstrip('=')

class SignupView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            name = serializer.validated_data['name']
            gender = serializer.validated_data['gender']
            date_of_birth = serializer.validated_data['date_of_birth']
            referral_code = serializer.validated_data.get('referrer_code')
            above_legal_age = serializer.validated_data['above_legal_age']
            terms_and_conditions = serializer.validated_data['terms_and_conditions']

            if CustomUser.objects.filter(email=email).exists():
                return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)

            user = CustomUser(
                email=email,
                name=name,
                gender=gender,
                date_of_birth=date_of_birth,
                above_legal_age=above_legal_age,
                terms_and_conditions=terms_and_conditions,
                is_verified=False
            )
            user.set_password(password)
            user.save()

            if referral_code:
                try:
                    referrer = CustomUser.objects.get(referral_code=referral_code)
                    Referral.objects.create(user=referrer, referred_user=user, reward_points=10)
                    referrer.reward_points = (referrer.reward_points or 0) + 10
                    referrer.save()
                except CustomUser.DoesNotExist:
                    pass

            verification_code = ''.join(random.choices(string.digits, k=6))
            user.verification_code = verification_code
            user.save()

            try:
                send_mail(
                    'Verify Your Email',
                    f'Your verification code is: {verification_code}',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
            except Exception as e:
                user.delete()
                return Response({'error': f'Failed to send verification email: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({'message': 'Verification code sent to email'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyEmailView(APIView):
    permission_classes = [AllowAny]
    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            code = serializer.validated_data['code']
            
            try:
                user = CustomUser.objects.get(email=email)
                if user.verification_code == code:
                    user.is_verified = True
                    user.verification_code = None
                    user.save()

                    token, _ = Token.objects.get_or_create(user=user)

                    return Response({
                        "message": "Email verified successfully",
                        "referral_code": user.referral_code,
                        "name": user.name,
                        "email": user.email,
                        "dob": user.date_of_birth.isoformat() if user.date_of_birth else '',
                        "gender": user.gender,
                        "picture_url": user.picture_url or '',
                        "user_token": token.key,
                        "above_legal_age": user.above_legal_age,
                        "terms_and_conditions": user.terms_and_conditions,
                        "hobbies": HobbySerializer(user.hobbies.all(), many=True).data,
                        "next_step": "permissions" 
                    }, status=status.HTTP_200_OK)
                else:
                    return Response(
                        {"detail": "Invalid verification code"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except CustomUser.DoesNotExist:
                return Response(
                    {"detail": "User not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class GoogleSignInView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        auth_token = request.data.get('auth_token')
        if not auth_token:
            return Response({'error': 'No auth token provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            idinfo = id_token.verify_oauth2_token(
                auth_token,
                google_requests.Request(),
                '675550706414-i9f1j9l4t9ifc40o9gnr59pt4kvdq907.apps.googleusercontent.com'
            )

            email = idinfo['email']
            name = idinfo.get('name', email.split('@')[0])
            picture_url = idinfo.get('picture', '')

            # Get or create the user
            user, created = CustomUser.objects.get_or_create(
                email=email,
                defaults={
                    'name': name,
                    'is_verified': True,
                    'gender': '',
                    'date_of_birth': None,
                    'picture_url': picture_url,
                    'above_legal_age': False,
                    'terms_and_conditions': False
                }
            )

            # Update fields only if the user already exists (not created)
            if not created:
                user.name = name
                user.is_verified = True
                user.picture_url = picture_url
                user.save()

            # Prepare data for the serializer, only including fields that are explicitly provided
            data = {
                'email': email,
                'name': name,
                'picture_url': picture_url,
            }

            # Only include these fields if they are explicitly provided in the request
            if 'referrer_code' in request.data:
                data['referrer_code'] = request.data.get('referrer_code', '')
            if 'above_legal_age' in request.data:
                data['above_legal_age'] = request.data.get('above_legal_age', user.above_legal_age)
            if 'terms_and_conditions' in request.data:
                data['terms_and_conditions'] = request.data.get('terms_and_conditions', user.terms_and_conditions)
            if 'gender' in request.data:
                data['gender'] = request.data.get('gender', user.gender)
            if 'date_of_birth' in request.data:
                data['date_of_birth'] = request.data.get('date_of_birth', user.date_of_birth)

            serializer = GoogleSignInSerializer(user, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            token, _ = Token.objects.get_or_create(user=user)

            print(user.qr_code_url)

            # Determine the next step based on user setup status
            if user.qr_code_url:  # If QR code exists, user has completed setup
                next_step = 'welcome'
            else:
                next_step = 'permissions'

            return Response({
                'message': 'Google Sign-In successful',
                'referral_code': user.referral_code,
                'name': user.name,
                'email': user.email,
                'dob': user.date_of_birth if user.date_of_birth else '',
                'gender': user.gender if user.gender else '',
                'picture_url': user.picture_url or '',
                'user_token': token.key,
                'above_legal_age': user.above_legal_age,
                'terms_and_conditions': user.terms_and_conditions,
                'hobbies': HobbySerializer(user.hobbies.all(), many=True).data,
                'next_step': next_step,
                'qr_code_url': user.qr_code_url or ''
            }, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response({'error': f'Invalid Google token: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        

class DeleteUserAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Only authenticated users can access

    def delete(self, request):
        try:
            user = request.user
            email = user.email
            
            # Delete QR code file if it exists
            if user.qr_code_url:
                # Extract the file path from the URL
                qr_file_path = user.qr_code_url.replace(settings.MEDIA_URL, '')
                full_path = os.path.join(settings.MEDIA_ROOT, qr_file_path)
                
                # Check if file exists and delete it
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        print(f"Successfully deleted QR code file: {full_path}")
                    except OSError as e:
                        print(f"Error deleting QR code file: {e}")
                else:
                    print(f"QR code file not found: {full_path}")
            
            # Now delete the user
            user.delete()
            
            return Response(
                {"message": "Your account has been successfully deleted."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to delete account: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

class UpdatePermissionsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = PermissionsSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Permissions updated successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class SetUsernameView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        action = request.data.get('action')  # 'save' or 'skip'

        if action == 'save':
            serializer = SetUsernameSerializer(user, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                user.last_username_change = timezone.now()
                user.save()
                qr_data = f"Username: {user.username}\nPicture URL: {user.picture_url}"
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        elif action == 'skip':
            qr_data = f"Name: {user.name}\nPicture URL: {user.picture_url}"
        else:
            return Response({"error": "Invalid action. Use 'save' or 'skip'"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill='black', back_color='white')

            # Ensure the qr_codes directory exists
            qr_codes_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
            if not os.path.exists(qr_codes_dir):
                os.makedirs(qr_codes_dir)

            # Save QR code to storage
            qr_filename = f"qr_codes/{user.email}_qr.png"
            qr_path = os.path.join(settings.MEDIA_ROOT, qr_filename)
            print(f"Saving QR code to: {qr_path}")  # Debug
            img.save(qr_path)
            
            if not os.path.exists(qr_path):
                return Response({"error": "Failed to save QR code"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            print(f"QR code saved successfully: {qr_path}")  # Debug

            # Generate URL for the QR code
            qr_url = f"{settings.MEDIA_URL}{qr_filename}"
            print(f"Generated QR URL: {qr_url}")  # Debug

            user.qr_code = qr_filename
            
            user.qr_code_url = qr_url
            user.save()

            return Response({
                "message": "Username processed successfully",
                "qr_code_url": qr_url,
                "next_step": "hobbies"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error generating QR code: {str(e)}")  # Debug
            return Response({"error": f"Failed to generate QR code: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response(
                {"error": "Email and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate user
        user = authenticate(username=email, password=password)  # Django uses username field for authentication

        if not user:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Check if user is verified
        if not user.is_verified:
            return Response(
                {"error": "Email not verified. Please verify your email first."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get or create token
        token, _ = Token.objects.get_or_create(user=user)

        # Return user data including the QR code URL
        return Response({
            "message": "Login successful",
            "referral_code": user.referral_code,
            "name": user.name,
            "email": user.email,
            "dob": user.date_of_birth.isoformat() if user.date_of_birth else '',
            "gender": user.gender,
            "picture_url": user.picture_url or '',
            "user_token": token.key,
            "above_legal_age": user.above_legal_age,
            "terms_and_conditions": user.terms_and_conditions,
            "hobbies": HobbySerializer(user.hobbies.all(), many=True).data,
            "next_step": "welcome" if user.hobbies.exists() else "hobbies",  
            "qr_code_url": user.qr_code_url or ''
        }, status=status.HTTP_200_OK)
    

class UpdateUserDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        data = request.data

        # Update user fields
        user.date_of_birth = data.get('dob', user.date_of_birth)
        user.gender = data.get('gender', user.gender)
        user.above_legal_age = data.get('above_legal_age', user.above_legal_age)
        user.terms_and_conditions = data.get('terms_and_conditions', user.terms_and_conditions)

        # Handle the referrer_code (the code of the user who referred this new user)
        referrer_code = data.get('referrer_code', '')
        if referrer_code:
            try:
                referrer = CustomUser.objects.get(referral_code=referrer_code)
                # Create a Referral record
                Referral.objects.create(user=referrer, referred_user=user, reward_points=10)
                # Award points to the referrer
                referrer.reward_points = (referrer.reward_points or 0) + 10
                referrer.save()
            except CustomUser.DoesNotExist:
                return Response(
                    {"error": "Invalid referral code"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        print("details: ", user.date_of_birth, user.gender, user.above_legal_age,user.terms_and_conditions )

        user.save()

        return Response(
            {"message": "User details updated successfully"},
            status=status.HTTP_200_OK
        )
    
passkey_challenges = {}

class PasskeyRegistrationOptionsView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasskeyRegistrationOptionsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Generate a random challenge
            challenge = secrets.token_bytes(32)
            passkey_challenges[email] = challenge


            print(f"Stored challenge for {email}: {challenge.hex()}")
            
            # Get existing credential IDs to exclude
            existing_credentials = PasskeyCredential.objects.filter(user=user)
            exclude_credentials = [
                {"id": cred.credential_id, "type": "public-key"} 
                for cred in existing_credentials
            ]
            
            # Generate registration options with user_id as bytes
            options = generate_registration_options(
                rp_id=request.get_host().split(':')[0],  # Remove port if any
                rp_name=f"{settings.APP_NAME}",
                user_id=str(user.id).encode('utf-8'),  # Convert user.id to bytes
                user_name=user.email,
                user_display_name=user.name or user.email,
                challenge=challenge,  # Ensure challenge is also bytes
                exclude_credentials=exclude_credentials,
                authenticator_selection=AuthenticatorSelectionCriteria(
                    user_verification="preferred"  # Set as "preferred", "required", or "discouraged"
                ),
                attestation="none"
            )
            
            options_dict = {
                "rp": {
                    "name": options.rp.name,
                    "id": options.rp.id
                },
                "user": {
                    "id": bytes_to_base64url(options.user.id),  # Decode bytes to string for JSON
                    "name": options.user.name,
                    "displayName": options.user.display_name
                },
                "challenge": bytes_to_base64url(options.challenge),
                "pubKeyCredParams": [
                    {"type": param.type, "alg": param.alg}
                    for param in options.pub_key_cred_params
                ],
                "timeout": options.timeout,
                "excludeCredentials": [
                    {"type": cred.type, "id": cred.id.decode('utf-8')}  # Decode bytes to string
                    for cred in options.exclude_credentials
                ],
                "authenticatorSelection": {
                    "userVerification": options.authenticator_selection.user_verification
                },
                "attestation": options.attestation
            }

            return Response(options_dict, status=status.HTTP_200_OK)
            
        except CustomUser.DoesNotExist:
            return Response(
                {"error": "User not found. Please create an account first."},
                status=status.HTTP_404_NOT_FOUND
            )
        
class PasskeyRegistrationVerifyView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasskeyRegistrationVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        attestation = serializer.validated_data['attestation']
        device_name = serializer.validated_data.get('device_name', 'Unknown device')
        
        try:
            user = CustomUser.objects.get(email=email)
            challenge = passkey_challenges.pop(email, None)
            
            print(f"Retrieved challenge for {email}: {challenge.hex() if challenge else None}")  # Log as hex
            
            if not challenge:
                return Response(
                    {"error": "Challenge expired or not found. Please try again."},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            try:
                rp_id = request.get_host().split(':')[0]
                origin = f"https://{request.get_host()}"
                
                if settings.DEBUG:
                    if request.headers.get('origin', '').startswith('http://'):
                        origin = request.headers.get('origin')
                
                verification = verify_registration_response(
                    credential=attestation,
                    expected_challenge=challenge,  # Already in bytes
                    expected_origin=origin,
                    expected_rp_id=rp_id,
                )
                
                # Store the credential
                PasskeyCredential.objects.create(
                    user=user,
                    credential_id=verification.credential_id,
                    public_key=verification.credential_public_key,
                    sign_count=verification.sign_count,
                    name=device_name,
                    last_used_at=timezone.now()
                )
                
                # Generate or get token
                token, _ = Token.objects.get_or_create(user=user)
                
                return Response({
                    "message": "Passkey registered successfully",
                    "user_token": token.key,
                    "referral_code": user.referral_code,
                    "name": user.name,
                    "email": user.email,
                    "dob": user.date_of_birth.isoformat() if user.date_of_birth else '',
                    "gender": user.gender,
                    "picture_url": user.picture_url or '',
                    "above_legal_age": user.above_legal_age,
                    "terms_and_conditions": user.terms_and_conditions,
                    "hobbies": HobbySerializer(user.hobbies.all(), many=True).data,
                    "qr_code_url": user.qr_code_url or '',
                    "next_step": "welcome" if user.hobbies.exists() else "hobbies"
                }, status=status.HTTP_200_OK)
                
            except InvalidRegistrationResponse as e:
                return Response({"error": f"Invalid registration: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
class PasskeyLoginOptionsView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasskeyLoginOptionsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data.get('email', None)
        
        # Generate a challenge
        challenge = secrets.token_urlsafe(32)
        
        allow_credentials = []
        if email:
            try:
                user = CustomUser.objects.get(email=email)
                credentials = PasskeyCredential.objects.filter(user=user)
                allow_credentials = [
                    {"id": cred.credential_id, "type": "public-key"} 
                    for cred in credentials
                ]
                
                # Store challenge with email
                passkey_challenges[email] = challenge
                
            except CustomUser.DoesNotExist:
                # Don't reveal that the user doesn't exist
                pass
        else:
            # For passwordless login without email, we store a global challenge
            passkey_challenges["global"] = challenge
        
        # Generate authentication options
        options = generate_authentication_options(
            rp_id=request.get_host().split(':')[0],  # Remove port if any
            challenge=challenge,
            allow_credentials=allow_credentials,
            user_verification="preferred"
        )
        
        return Response(options, status=status.HTTP_200_OK)
    

class PasskeyLoginVerifyView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        serializer = PasskeyLoginVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        assertion = serializer.validated_data['assertion']
        
        try:
            user = CustomUser.objects.get(email=email)
            
            # Get the challenge (either email-specific or global)
            challenge = passkey_challenges.pop(email, passkey_challenges.pop("global", None))
            
            if not challenge:
                return Response(
                    {"error": "Challenge expired or not found. Please try again."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                # Find the credential by ID
                credential_id = assertion['id']
                credential = PasskeyCredential.objects.get(
                    user=user, 
                    credential_id=credential_id
                )
                
                rp_id = request.get_host().split(':')[0]  # Remove port if any
                origin = f"https://{request.get_host()}"
                
                # For development, allow http origin if not in production
                if settings.DEBUG:
                    if request.headers.get('origin', '').startswith('http://'):
                        origin = request.headers.get('origin')
                
                verification = verify_authentication_response(
                    credential=assertion,
                    expected_challenge=challenge,
                    expected_origin=origin,
                    expected_rp_id=rp_id,
                    credential_public_key=credential.public_key,
                    credential_current_sign_count=credential.sign_count,
                    require_user_verification=False
                )
                
                # Update the counter to prevent replay attacks
                credential.sign_count = verification.new_sign_count
                credential.last_used_at = timezone.now()
                credential.save()
                
                # Generate or get token
                token, _ = Token.objects.get_or_create(user=user)
                
                # Return the user information similar to your existing login view
                return Response({
                    "message": "Login successful with passkey",
                    "referral_code": user.referral_code,
                    "name": user.name,
                    "email": user.email,
                    "dob": user.date_of_birth.isoformat() if user.date_of_birth else '',
                    "gender": user.gender,
                    "picture_url": user.picture_url or '',
                    "user_token": token.key,
                    "above_legal_age": user.above_legal_age,
                    "terms_and_conditions": user.terms_and_conditions,
                    "hobbies": HobbySerializer(user.hobbies.all(), many=True).data,
                    "next_step": "welcome" if user.hobbies.exists() else "hobbies",
                    "qr_code_url": user.qr_code_url or ''
                }, status=status.HTTP_200_OK)
                
            except PasskeyCredential.DoesNotExist:
                return Response({"error": "Invalid credential"}, status=status.HTTP_400_BAD_REQUEST)
            except InvalidAuthenticationResponse as e:
                return Response({"error": f"Invalid authentication: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)
                
        except CustomUser.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        
from django.shortcuts import render


class PasskeyTestPageView(APIView):
    permission_classes = [AllowAny]  # Allow anyone to access this page

    def get(self, request):
        return render(request, 'signup/passkey_test_page.html')