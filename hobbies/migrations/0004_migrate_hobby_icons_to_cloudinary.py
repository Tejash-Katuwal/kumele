# hobbies/migrations/0004_migrate_hobby_icons_to_cloudinary.py
from django.db import migrations
import os
from django.core.files import File
from cloudinary.uploader import upload
from django.conf import settings
import cloudinary  # Add this import

def migrate_hobby_icons_to_cloudinary(apps, schema_editor):
    # Explicitly configure Cloudinary
    cloudinary.config(
        cloud_name="dostiek8h",
        api_key="441397572511426",
        api_secret="SLKq7Ned7ULfz1LoMxWQztvCPms"
    )

    Hobby = apps.get_model('hobbies', 'Hobby')
    
    for hobby in Hobby.objects.all():
        if hobby.icon and hobby.icon.url.startswith('/media/'):
            print(f"Migrating icon for {hobby.name}...")
            icon_path = os.path.join(settings.MEDIA_ROOT, hobby.icon.name)
            if os.path.exists(icon_path):
                with open(icon_path, 'rb') as f:
                    # Upload to Cloudinary
                    result = upload(f, folder='hobby_icons', public_id=os.path.splitext(hobby.icon.name.split('/')[-1])[0])
                    # Update the icon field with the Cloudinary public ID
                    hobby.icon = result['public_id']
                    hobby.save()
            else:
                print(f"Icon file not found: {icon_path}")

def reverse_migration(apps, schema_editor):
    # Optionally, you can implement logic to revert the migration
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('hobbies', '0003_auto_20250405_1836'),  # Adjust based on your previous migration
    ]

    operations = [
        migrations.RunPython(migrate_hobby_icons_to_cloudinary, reverse_migration),
    ]