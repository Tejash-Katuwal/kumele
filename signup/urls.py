from django.urls import path
from .views import SignupView, VerifyEmailView, GoogleSignInView, DeleteUserAPIView, UpdatePermissionsView, SetUsernameView, LoginView

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    path('google-signin/', GoogleSignInView.as_view(), name='google_signin'),
    path('user/delete/', DeleteUserAPIView.as_view(), name='delete-user'),
    path('update-permissions/', UpdatePermissionsView.as_view(), name='update-permissions'),
    path('set-username/', SetUsernameView.as_view(), name='set-username'),
    path('login/', LoginView.as_view(), name='login'),
]