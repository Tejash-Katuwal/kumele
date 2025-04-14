from .models import TwoFactorAuth
from rest_framework import serializers
from signup.models import CustomUser


class TwoFactorEnableSerializer(serializers.Serializer):
    verification_code = serializers.CharField(required=True)

class TwoFactorStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['two_factor_enabled']