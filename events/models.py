from django.db import models
from django.utils import timezone
from signup.models import CustomUser
from hobbies.models import Hobby


class GuestPricing(models.Model):
    min_guests = models.IntegerField()
    max_guests = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = ('min_guests', 'max_guests')

    def __str__(self):
        return f"{self.min_guests}-{self.max_guests} guests: ${self.price}"

class Event(models.Model):
    PAYMENT_TYPES = (
        ('FREE', 'Free'),
        ('CARD', 'Card Payment'),
        ('CASH', 'Cash on Entry'),
    )

    creator = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_events')
    category = models.ForeignKey(Hobby, on_delete=models.SET_NULL, null=True, related_name='events')
    name = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    image = models.ImageField(upload_to='event_images/', blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    duration_hours = models.FloatField()  # e.g., 24 hours
    age_range_min = models.IntegerField()
    age_range_max = models.IntegerField()
    max_guests = models.IntegerField()  # e.g., 5, 40, 60, etc.
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  # Price based on guest range
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPES, default='FREE')
    street = models.CharField(max_length=200)
    home_number = models.CharField(max_length=50)
    district = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=20, blank=True)
    state = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)  # Active after payment (for paid events)

    def __str__(self):
        return self.name

class EventPayment(models.Model):
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='payment')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateTimeField(null=True, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)  # For dummy payment

    def __str__(self):
        return f"Payment for {self.event.name}"

class UserAvailability(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='availabilities')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    def __str__(self):
        return f"{self.user.username} availability"
    

class NotificationPreference(models.Model):
    NOTIFICATION_TYPES = (
        ('24_HOURS', '24 Hours (Free)'),
        ('48_HOURS', '48 Hours ($6.00)'),
        ('7_DAYS', '7 Days ($13.70)'),
    )

    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='notification_preference')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='24_HOURS')
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Notification for {self.event.name}: {self.notification_type}"

class Cart(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)

    def get_total_cost(self):
        return sum(item.get_cost() for item in self.items.all())

    def __str__(self):
        return f"Cart for {self.user.username}"

class CartItem(models.Model):
    ITEM_TYPES = (
        ('EVENT', 'Event Creation'),
        ('NOTIFICATION', 'Notification'),
    )

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    item_type = models.CharField(max_length=20, choices=ITEM_TYPES)
    event_data = models.JSONField(null=True, blank=True)  # Store pending event data for EVENT type
    notification_type = models.CharField(max_length=20, choices=NotificationPreference.NOTIFICATION_TYPES, null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2)

    def get_cost(self):
        return self.cost

    def __str__(self):
        return f"{self.item_type} item in cart {self.cart.id}"
    

class EventAttendance(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='attendees')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='attended_events')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('event', 'user')  # Prevent duplicate joins

    def __str__(self):
        return f"{self.user} joined {self.event}"