# paypalconnections/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone

class PayPalAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='paypal_account')
    paypal_email = models.EmailField()
    account_id = models.CharField(max_length=100)  # PayPal's unique identifier for the account
    access_token = models.CharField(max_length=255)
    refresh_token = models.CharField(max_length=255)
    token_expiry = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    @property
    def token_valid(self):
        """Check if the access token is still valid"""
        return self.token_expiry > timezone.now()
    
    def __str__(self):
        return f"PayPal account for {self.user.email}"
    
    class Meta:
        verbose_name = "PayPal Account"
        verbose_name_plural = "PayPal Accounts"


class PayPalTransaction(models.Model):
    """Optional: For tracking PayPal transactions"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded')
    ]
    
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_transactions')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    transaction_id = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    event_reference = models.CharField(max_length=100, blank=True, null=True)  # Reference to the event
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"PayPal transaction: {self.sender.email} to {self.recipient.email} ({self.amount} {self.currency})"