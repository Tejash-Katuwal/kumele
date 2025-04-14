from django.db import models
from signup.models import CustomUser


class TwoFactorAuth(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='two_factor')
    secret_key = models.CharField(max_length=50)
    backup_codes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)


    def __str__(self):
        return f"2FA for {self.user.email}"