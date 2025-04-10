from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from signup.models import CustomUser
from .serializers import (UserSearchSerializer, 
    FollowerFollowingSerializer, 
    UserProfileSerializer, 
    ChangePasswordSerializer,
    UpdateProfileImageSerializer)
from django.db.models import Q
from django.shortcuts import get_object_or_404
import qrcode
import os
from django.conf import settings
from django.core.files.storage import default_storage
import time



class UserSearchAPIView(APIView):
    permission_classes = [IsAuthenticated]  # Optional: remove if public access is desired

    def get(self, request, format=None):
        query = request.GET.get('q', '').strip()
        if not query:
            return Response({"error": "Search query is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Search by username or name (case-insensitive)
        users = CustomUser.objects.filter(
            Q(username__icontains=query) | Q(name__icontains=query)
        ).distinct()

        serializer = UserSearchSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    

class FollowUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, username, format=None):
        user_to_follow = get_object_or_404(CustomUser, username=username)
        
        if request.user == user_to_follow:
            return Response({"error": "You cannot follow yourself"}, status=status.HTTP_400_BAD_REQUEST)
        
        if user_to_follow in request.user.following.all():
            return Response({"message": "You are already following this user"}, status=status.HTTP_200_OK)
        
        request.user.following.add(user_to_follow)
        return Response({"message": f"You are now following {username}"}, status=status.HTTP_200_OK)
    

class FollowerFollowingAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, username, format=None):
        user = get_object_or_404(CustomUser, username=username)
        serializer = FollowerFollowingSerializer(user)
        data = [
            {'followers': serializer.data['followers']},
            {'followings': serializer.data['followings']}
        ]
        return Response(data, status=status.HTTP_200_OK)
    

class EditBioView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = UserProfileSerializer(user, data={'bio': request.data.get('bio')}, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Bio updated successfully", "bio": serializer.data['bio']}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({"error": "Old password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class ToggleSoundNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        enabled = request.data.get('enabled', not user.sound_notifications)  # Toggle if not specified
        user.sound_notifications = bool(enabled)
        user.save()
        return Response({
            "message": f"Sound notifications {'enabled' if user.sound_notifications else 'disabled'}",
            "sound_notifications": user.sound_notifications
        }, status=status.HTTP_200_OK)
    
class ToggleEmailNotificationsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        enabled = request.data.get('enabled', not user.email_notifications)  # Toggle if not specified
        user.email_notifications = bool(enabled)
        user.save()
        return Response({
            "message": f"Email notifications {'enabled' if user.email_notifications else 'disabled'}",
            "email_notifications": user.email_notifications
        }, status=status.HTTP_200_OK)
    
class ChangeThemeModeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        theme = request.data.get('theme_mode')
        if theme not in ['bright', 'night']:
            return Response({"error": "Invalid theme mode. Use 'bright' or 'night'"}, status=status.HTTP_400_BAD_REQUEST)
        user.theme_mode = theme
        user.save()
        return Response({"message": f"Theme changed to {theme}", "theme_mode": user.theme_mode}, status=status.HTTP_200_OK)
    

class UpdateProfileImageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        # Check if file is in the request
        if 'profile_pic' not in request.FILES:
            return Response({"error": "No profile_pic provided"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get the uploaded file
        uploaded_file = request.FILES['profile_pic']
        
        # Define the file path for the profile picture
        file_extension = os.path.splitext(uploaded_file.name)[1]  # e.g., '.jpg'
        file_name = f"profile_pics/{user.email}_profile{file_extension}"
        file_path = os.path.join(settings.MEDIA_ROOT, file_name)

        # Ensure the profile_pics directory exists
        profile_pics_dir = os.path.join(settings.MEDIA_ROOT, 'profile_pics')
        if not os.path.exists(profile_pics_dir):
            os.makedirs(profile_pics_dir)

        # Save the uploaded file
        with open(file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)
                
        # Generate URL with timestamp for cache busting
        timestamp = int(time.time())
        profile_pic_url = f"{settings.MEDIA_URL}{file_name}?t={timestamp}"
        print("profile_pic_url: ", profile_pic_url)
        
        # Update serializer to use profile_pic_url instead of picture_url
        serializer = UpdateProfileImageSerializer(user, data={'profile_pic_url': profile_pic_url}, partial=True)
        if serializer.is_valid():
            serializer.save()  # Updates user.profile_pic_url in the database
            
            # Refresh the user object from the database
            user.refresh_from_db()
            
            # Check if the update was successful
            if user.profile_pic_url != profile_pic_url:
                return Response({"error": "Failed to update picture URL"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Regenerate QR code with the new picture URL
            picture_url_to_use = user.get_picture_url()  # Use the helper method
            qr_data = (
                f"Username: {user.username}\nPicture URL: {picture_url_to_use}"
                if user.username
                else f"Name: {user.name}\nPicture URL: {picture_url_to_use}"
            )

            try:
                # Generate new QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(qr_data)
                qr.make(fit=True)
                img = qr.make_image(fill='black', back_color='white')

                # Ensure qr_codes directory exists
                qr_codes_dir = os.path.join(settings.MEDIA_ROOT, 'qr_codes')
                if not os.path.exists(qr_codes_dir):
                    os.makedirs(qr_codes_dir)

                # Overwrite the existing QR code file
                qr_filename = f"qr_codes/{user.email}_qr.png"
                qr_path = os.path.join(settings.MEDIA_ROOT, qr_filename)
                img.save(qr_path)

                # Wait briefly to ensure the file is written
                time.sleep(0.1)  # Small delay to ensure file system sync

                if not os.path.exists(qr_path):
                    return Response({"error": "Failed to save QR code"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                # Generate QR code URL with a cache-busting query parameter
                qr_url = f"{settings.MEDIA_URL}{qr_filename}?t={timestamp}"

                # Update user fields and refresh from DB
                user.qr_code = qr_filename
                user.qr_code_url = qr_url
                user.save()

                # Refresh the user instance to ensure latest data
                user.refresh_from_db()

                return Response({
                    "message": "Profile image updated and QR code regenerated",
                    "picture_url": picture_url_to_use,  # Return the appropriate URL
                    "qr_code_url": user.qr_code_url
                }, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({"error": f"Failed to regenerate QR code: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)