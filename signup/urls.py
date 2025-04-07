from django.urls import path
from .views import (SignupView,
    VerifyEmailView, 
    GoogleSignInView, 
    DeleteUserAPIView, 
    UpdatePermissionsView, 
    SetUsernameView, 
    LoginView, 
    UpdateUserDetailsView,
    PasskeyRegistrationOptionsView,
    PasskeyRegistrationVerifyView,
    PasskeyLoginOptionsView,
    PasskeyLoginVerifyView,
)

urlpatterns = [
    path('signup/', SignupView.as_view(), name='signup'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify_email'),
    path('google-signin/', GoogleSignInView.as_view(), name='google_signin'),
    path('user/delete/', DeleteUserAPIView.as_view(), name='delete-user'),
    path('update-permissions/', UpdatePermissionsView.as_view(), name='update-permissions'),
    path('set-username/', SetUsernameView.as_view(), name='set-username'),
    path('login/', LoginView.as_view(), name='login'),
    path('update-user-details/', UpdateUserDetailsView.as_view(), name='update-user-details'),
    path('passkey/register/options/', PasskeyRegistrationOptionsView.as_view(), name='passkey_register_options'),
    path('passkey/register/verify/', PasskeyRegistrationVerifyView.as_view(), name='passkey_register_verify'),
    path('passkey/login/options/', PasskeyLoginOptionsView.as_view(), name='passkey_login_options'),
    path('passkey/login/verify/', PasskeyLoginVerifyView.as_view(), name='passkey_login_verify'),

]