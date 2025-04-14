from django.urls import path
from .views import (UserSearchAPIView,
    FollowUserAPIView,
    FollowerFollowingAPIView,
    EditBioView,
    ChangePasswordView,
    ToggleSoundNotificationsView,
    ToggleEmailNotificationsView,
    ChangeThemeModeView,
    UpdateProfileImageView,
    UserProfileView)

urlpatterns = [
    path('search/', UserSearchAPIView.as_view(), name='user_search_api'),
    path('<str:username>/follow/', FollowUserAPIView.as_view(), name='follow_user_api'),
    path('<str:username>/follows/', FollowerFollowingAPIView.as_view(), name='follower_following_api'), 
    path('user-profile/', UserProfileView.as_view(), name='user-profile'),
    path('edit-bio/', EditBioView.as_view(), name='edit_bio'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('toggle-sound-notifications/', ToggleSoundNotificationsView.as_view(), name='toggle_sound_notifications'),
    path('toggle-email-notifications/', ToggleEmailNotificationsView.as_view(), name='toggle_email_notifications'),
    path('change-theme/', ChangeThemeModeView.as_view(), name='change_theme'),
    path('update-profile-image/', UpdateProfileImageView.as_view(), name='update_profile_image'),
]