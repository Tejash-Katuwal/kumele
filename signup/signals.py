# signup/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import CustomUser
import cloudinary.uploader

@receiver(post_delete, sender=CustomUser)
def delete_cloudinary_file(sender, instance, **kwargs):
    if instance.qr_code:
        public_id = instance.qr_code.name.split('.')[0]  # Extract public ID
        cloudinary.uploader.destroy(public_id)