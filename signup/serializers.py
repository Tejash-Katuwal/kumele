from django.utils import timezone
from rest_framework import serializers
from .models import CustomUser, Medal, Referral, PasskeyCredential
from hobbies.serializers import HobbySerializer

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    referrer_code = serializers.CharField(required=False, write_only=True)
    above_legal_age = serializers.BooleanField(write_only=True)  # Required
    terms_and_conditions = serializers.BooleanField(write_only=True)  # Required

    class Meta:
        model = CustomUser
        fields = ['name', 'email', 'password', 'confirm_password', 'gender', 'date_of_birth', 
                  'referrer_code', 'above_legal_age', 'terms_and_conditions', 'hobbies']

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match")
        if not data.get('above_legal_age'):
            raise serializers.ValidationError("You must confirm you are above the legal age")
        if not data.get('terms_and_conditions'):
            raise serializers.ValidationError("You must accept the terms and conditions")
        return data

    def create(self, validated_data):
        referrer_code = validated_data.pop('referrer_code', None)
        validated_data.pop('confirm_password')
        above_legal_age = validated_data.pop('above_legal_age')
        terms_and_conditions = validated_data.pop('terms_and_conditions')

        user = CustomUser.objects.create_user(
            **validated_data,
            above_legal_age=above_legal_age,
            terms_and_conditions=terms_and_conditions
        )

        if referrer_code:
            try:
                referrer = CustomUser.objects.get(referral_code=referrer_code)
                Referral.objects.create(user=referrer, referred_user=user, reward_points=10)
                referrer.reward_points += 10
                referrer.save()
            except CustomUser.DoesNotExist:
                pass

        return user

class VerifyEmailSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class GoogleSignInSerializer(serializers.ModelSerializer):
    referrer_code = serializers.CharField(required=False, write_only=True, allow_blank=True)  # Add allow_blank=True
    above_legal_age = serializers.BooleanField(write_only=True, required=False, default=False)
    terms_and_conditions = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = CustomUser
        fields = ['name', 'email', 'gender', 'date_of_birth', 'referrer_code', 
                  'above_legal_age', 'terms_and_conditions', 'hobbies']

    def create(self, validated_data):
        email = validated_data['email']
        name = validated_data.get('name', '')
        referrer_code = validated_data.pop('referrer_code', None)  # None if not provided
        above_legal_age = validated_data.pop('above_legal_age', False)
        terms_and_conditions = validated_data.pop('terms_and_conditions', False)

        user, created = CustomUser.objects.get_or_create(email=email, defaults={
            'name': name,
            'is_verified': True,
            'gender': '',
            'date_of_birth': None,
            'above_legal_age': above_legal_age,
            'terms_and_conditions': terms_and_conditions
        })

        if not created:
            user.name = name
            user.is_verified = True
            user.save()

        if referrer_code:  # Only process if referrer_code is provided and non-empty
            try:
                referrer = CustomUser.objects.get(referral_code=referrer_code)
                Referral.objects.create(user=referrer, referred_user=user, reward_points=10)
                referrer.reward_points += 10
                referrer.save()
            except CustomUser.DoesNotExist:
                pass

        return user
    
class PermissionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['allow_photos', 'allow_notifications', 'allow_location']

    def validate(self, data):
        # Ensure valid choices are provided
        if 'allow_photos' in data and data['allow_photos'] not in ['none', 'selected', 'all']:
            raise serializers.ValidationError("Invalid value for allow_photos")
        if 'allow_location' in data and data['allow_location'] not in ['none', 'while_using', 'once']:
            raise serializers.ValidationError("Invalid value for allow_location")
        return data
    
class SetUsernameSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['username']

    def validate_username(self, value):
        user = self.instance
        if user.username and user.last_username_change:
            # Check if 3 months have passed since last username change
            from datetime import timedelta
            if (timezone.now() - user.last_username_change) < timedelta(days=90):
                raise serializers.ValidationError("Usernames can only be changed every 3 months")
        return value
    
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={'input_type': 'password'})
    hobbies = HobbySerializer(many=True, read_only=True)  # Add hobbies to response

    class Meta:
        model = CustomUser
        fields = ['email', 'password', 'hobbies']


class PasskeyRegistrationOptionsSerializer(serializers.Serializer):
    email = serializers.EmailField()
    device_name = serializers.CharField(max_length=100, required=False)

class PasskeyRegistrationVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    attestation = serializers.JSONField()
    device_name = serializers.CharField(max_length=100, required=False)

class PasskeyLoginOptionsSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)  # Optional, user might not provide email upfront

class PasskeyLoginVerifySerializer(serializers.Serializer):
    # email = serializers.EmailField()
    assertion = serializers.JSONField()


class MedalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medal
        fields = ['medal_type', 'awarded_at', 'discount_percentage', 'discount_expires_at']