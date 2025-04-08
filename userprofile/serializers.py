from rest_framework import serializers
from signup.models import CustomUser


class UserSearchSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['picture_url', 'display_name']

    def get_display_name(self, obj):
        # Return username if available, otherwise use name
        return obj.username if obj.username else obj.name
    

class UserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = ['picture_url', 'display_name']

    def get_display_name(self, obj):
        return obj.username if obj.username else obj.name


class FollowerFollowingSerializer(serializers.ModelSerializer):
    followers = UserSerializer(many=True)
    followings = UserSerializer(many=True, source='following')

    class Meta:
        model = CustomUser
        fields = ['followers', 'followings']


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'bio',
            'sound_notifications',
            'email_notifications',
            'theme_mode',
        ]


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    confirm_new_password = serializers.CharField(required=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError("New passwords do not match")
        return data
    

class UpdateProfileImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['picture_url']