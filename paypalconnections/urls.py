from django.urls import path
from .views import (ConnectPayPalView, 
    PayPalOnboardingCallbackView, 
    PayPalStatusView, 
    DisconnectPayPalView,
    PayPalWebhookView
    )

urlpatterns = [
    path("paypal/connect/", ConnectPayPalView.as_view(), name="paypal-connect"),
    path("paypal-onboarding-callback/", PayPalOnboardingCallbackView.as_view(), name="paypal-onboarding-callback"),
    path('paypal-status/', PayPalStatusView.as_view(), name='paypal-status'),
    path('paypal-disconnect/', DisconnectPayPalView.as_view(), name='paypal-disconnect'),
    path("webhooks/paypal/", PayPalWebhookView.as_view(), name="paypal-webhook"),
]