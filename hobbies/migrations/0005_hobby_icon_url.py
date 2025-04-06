# hobbies/migrations/0005_populate_hobby_icon_urls.py
from django.db import migrations

def populate_icon_urls(apps, schema_editor):
    Hobby = apps.get_model('hobbies', 'Hobby')
    
    for hobby in Hobby.objects.all():
        if hobby.icon:
            if hobby.icon.name.startswith('hobby_icons/'):
                # This is a Cloudinary public ID
                hobby.icon_url = f"https://res.cloudinary.com/dostiek8h/image/upload/{hobby.icon}"
                hobby.save()
            elif hasattr(hobby.icon, 'url') and hobby.icon.url:
                # Handle case where icon may already be a full URL
                if hobby.icon.url.startswith('/media/'):
                    # For icons that weren't migrated to Cloudinary
                    public_id = hobby.icon.name
                    hobby.icon_url = f"https://res.cloudinary.com/dostiek8h/image/upload/{public_id}"
                    hobby.save()
                else:
                    # Already a full URL
                    hobby.icon_url = hobby.icon.url
                    hobby.save()

def reverse_migration(apps, schema_editor):
    Hobby = apps.get_model('hobbies', 'Hobby')
    for hobby in Hobby.objects.all():
        hobby.icon_url = None
        hobby.save()

class Migration(migrations.Migration):
    dependencies = [
        ('hobbies', '0004_migrate_hobby_icons_to_cloudinary'),  # Update with the actual previous migration
    ]

    operations = [
        migrations.RunPython(populate_icon_urls, reverse_migration),
    ]