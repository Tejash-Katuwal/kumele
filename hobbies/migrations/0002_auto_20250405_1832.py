from django.db import migrations
import os
from django.core.files import File

def add_initial_hobbies(apps, schema_editor):
    Hobby = apps.get_model('hobbies', 'Hobby')
    
    # List of hobbies and their corresponding icon filenames
    hobbies_data = [
        ('Van Life', 'vans.png'),
        ('Sports', 'sports.png'),
        ('Pets', 'pets.png'),
        ('Gaming', 'gaming.png'),
        ('Foodie', 'foodie.png'),
    ]
    
    # Path to the temporary directory where your icons are stored
    temp_icon_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'temp_icons')
    
    for hobby_name, icon_filename in hobbies_data:
        hobby = Hobby(name=hobby_name)
        icon_path = os.path.join(temp_icon_dir, icon_filename)
        
        if os.path.exists(icon_path):
            with open(icon_path, 'rb') as f:
                hobby.icon.save(icon_filename, File(f), save=True)
        else:
            print(f"Icon file not found: {icon_path}")
        
        hobby.save()

def remove_initial_hobbies(apps, schema_editor):
    Hobby = apps.get_model('hobbies', 'Hobby')
    Hobby.objects.filter(name__in=[
        'Van Life', 'Sports', 'Pets', 'Gaming', 'Foodie'
    ]).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('hobbies', '0001_initial'),  # Adjust based on your previous migration
    ]

    operations = [
        migrations.RunPython(add_initial_hobbies, remove_initial_hobbies),
    ]