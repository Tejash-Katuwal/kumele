from rest_framework import serializers
from hobbies.models import Hobby
from .models import Event, EventPayment, UserAvailability, GuestPricing
from hobbies.serializers import HobbySerializer
from django.utils import timezone

class GuestPricingSerializer(serializers.ModelSerializer):
    class Meta:
        model = GuestPricing
        fields = ['id', 'min_guests', 'max_guests', 'price']

class EventSerializer(serializers.ModelSerializer):
    category = HobbySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Hobby.objects.all(), source='category', write_only=True
    )
    current_attendees = serializers.SerializerMethodField()
    is_joinable = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'creator', 'category', 'category_id', 'name', 'subtitle', 'description',
            'image', 'start_time', 'end_time', 'duration_hours', 'age_range_min',
            'age_range_max', 'max_guests', 'current_attendees', 'is_joinable', 'price',
            'payment_type', 'street', 'home_number', 'district', 'postal_code', 'state',
            'created_at', 'is_active'
        ]
        read_only_fields = ['creator', 'created_at', 'is_active']

    def get_current_attendees(self, obj):
        return obj.attendees.count()  # Count the number of users who have joined

    def get_is_joinable(self, obj):
        # Check if the event has reached its max guests limit
        return obj.attendees.count() < obj.max_guests

    def validate(self, data):
        if data['start_time'] <= timezone.now():
            raise serializers.ValidationError("Event start time must be in the future.")
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError("Event end time must be after start time.")
        if data['age_range_max'] <= data['age_range_min']:
            raise serializers.ValidationError("Maximum age must be greater than minimum age.")
        return data

class EventPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventPayment
        fields = ['id', 'event', 'user', 'amount', 'is_paid', 'payment_date', 'transaction_id']
        read_only_fields = []

class UserAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAvailability
        fields = ['id', 'user', 'start_time', 'end_time']
        read_only_fields = ['user']

