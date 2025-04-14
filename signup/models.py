from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
from encrypted_model_fields.fields import EncryptedCharField

class CustomUser(AbstractUser):
    name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=[
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Non-Binary', 'Non-Binary'),
    ], blank=True, default='')  # Allow blank for Google
    date_of_birth = models.DateField(null=True, blank=True)  # Allow null for Google
    picture_url = models.URLField(max_length=200, blank=True, default='')
    above_legal_age = models.BooleanField(default=False)  # New field
    terms_and_conditions = models.BooleanField(default=False)  # New field
    is_verified = models.BooleanField(default=False)
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    referral_code = models.CharField(max_length=36, unique=True, default=uuid.uuid4)
    reward_points = models.IntegerField(default=0)
    profile_pic_url = models.URLField(max_length=200, blank=True, default='')

    hobbies = models.ManyToManyField('hobbies.Hobby', related_name='users', blank=True)
    following = models.ManyToManyField('self', symmetrical=False, related_name='followers', blank=True)

    allow_photos = models.CharField(max_length=20, choices=[
        ('none', 'None'),
        ('selected', 'Selected Photos'),
        ('all', 'All Photos'),
    ], default='none')
    
    allow_notifications = models.BooleanField(default=False)
    
    allow_location = models.CharField(max_length=20, choices=[
        ('none', 'None'),
        ('while_using', 'While Using App'),
        ('once', 'Once'),
    ], default='none')
    
    # New fields for username change tracking and QR code
    last_username_change = models.DateTimeField(null=True, blank=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)
    qr_code_url = models.URLField(max_length=200, blank=True, default='')
    two_factor_enabled = models.BooleanField(default=False)

    bio = models.TextField(max_length=500, blank=True, default="")  
    sound_notifications = models.BooleanField(default=True) 
    email_notifications = models.BooleanField(default=False)
    theme_mode = models.CharField(max_length=10, choices=[
        ('bright', 'Bright'),
        ('night', 'Night'),
    ], default='bright')

    paypal_access_token = EncryptedCharField(max_length=255, blank=True, null=True)
    paypal_refresh_token = EncryptedCharField(max_length=255, blank=True, null=True)
    paypal_account_id = models.CharField(max_length=100, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        # If notifications are disabled, also disable sound and email notifications
        if not self.allow_notifications:
            self.sound_notifications = False
            self.email_notifications = False
        super().save(*args, **kwargs)

    def get_picture_url(self):
        """Return profile_pic_url if available, otherwise fall back to picture_url"""
        return self.profile_pic_url if self.profile_pic_url else self.picture_url

class Referral(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='referrals')  # Referrer
    referred_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='referred_by')
    reward_points = models.IntegerField(default=10)

    def __str__(self):
        return f"{self.user.email} referred {self.referred_user.email}"
    

class PasskeyCredential(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='passkeys')
    credential_id = models.BinaryField(unique=True)
    public_key = models.BinaryField()
    sign_count = models.BigIntegerField(default=0)
    name = models.CharField(max_length=100, blank=True)  # Device or credential name
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['credential_id']),
            models.Index(fields=['user']),
        ]
        
    def __str__(self):
        return f"Passkey for {self.user.email} ({self.name})"
    

class Medal(models.Model):
    MEDAL_TYPES = (
        ('GOLD', 'Gold'),
        ('SILVER', 'Silver'),
        ('BRONZE', 'Bronze'),
    )

    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='medals')
    medal_type = models.CharField(max_length=10, choices=MEDAL_TYPES)
    awarded_at = models.DateTimeField(auto_now_add=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    discount_expires_at = models.DateTimeField(null=True, blank=True)
    period_start = models.DateTimeField()  # Start of the month
    period_end = models.DateTimeField()    # End of the month

    class Meta:
        unique_together = ('user', 'medal_type', 'period_start')  # No duplicate medals per type per period

    def __str__(self):
        return f"{self.user.email} - {self.medal_type} ({self.period_start.strftime('%Y-%m')})"