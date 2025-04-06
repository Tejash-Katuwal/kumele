from rest_framework import serializers
from .models import Hobby
from signup.models import CustomUser

class HobbySerializer(serializers.ModelSerializer):
    class Meta:
        model = Hobby
        fields = ['id', 'name', 'icon']
        # Ensure 'icon' is writable as a file upload and readable as a URL
        extra_kwargs = {
            'icon': {'required': False}  # Make icon optional if desired
        }

class SelectHobbiesSerializer(serializers.ModelSerializer):
    hobbies = serializers.PrimaryKeyRelatedField(
        queryset=Hobby.objects.all(),
        many=True,
        write_only=True
    )

    class Meta:
        model = CustomUser
        fields = ['hobbies']

    def validate_hobbies(self, value):
        if len(value) < 1:
            raise serializers.ValidationError("You must select at least one hobby.")
        if len(value) > 5:
            raise serializers.ValidationError("You can select up to 5 hobbies only.")
        return value