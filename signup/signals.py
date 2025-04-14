from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from .models import CustomUser
import os
from django.conf import settings
from events.models import Event, EventAttendance
from .utils import MedalManager

@receiver(post_delete, sender=CustomUser)
def delete_local_qr_file(sender, instance, **kwargs):
    if instance.qr_code:
        # Get the file path
        file_path = os.path.join(settings.MEDIA_ROOT, instance.qr_code.name)
        # Check if file exists and delete it
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                print(f"Error deleting QR code file: {e}")


@receiver(post_save, sender=Event)
@receiver(post_save, sender=EventAttendance)
def update_medals(sender, instance, created, **kwargs):
    if created:
        user = instance.creator if sender == Event else instance.user
        MedalManager.assign_medals(user)