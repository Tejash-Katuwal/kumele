from django.db import migrations
import os
from django.core.files import File

def update_hobby_icons(apps, schema_editor):
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
    
    # Iterate directly over the list of tuples
    for hobby_name, icon_filename in hobbies_data:  # Remove .items()
        try:
            hobby = Hobby.objects.get(name=hobby_name)
            icon_path = os.path.join(temp_icon_dir, icon_filename)
            
            if os.path.exists(icon_path):
                with open(icon_path, 'rb') as f:
                    hobby.icon.save(icon_filename, File(f), save=True)
                print(f"Updated icon for {hobby_name}")
            else:
                print(f"Icon file not found: {icon_path}")
        except Hobby.DoesNotExist:
            print(f"Hobby not found: {hobby_name}")

def remove_hobby_icons(apps, schema_editor):
    Hobby = apps.get_model('hobbies', 'Hobby')
    # Remove the icons but keep the hobbies
    for hobby in Hobby.objects.all():
        if hobby.icon:
            hobby.icon.delete(save=True)
            print(f"Removed icon for {hobby.name}")

class Migration(migrations.Migration):
    dependencies = [
        ('hobbies', '0002_auto_20250405_1832'),  # Adjust based on your previous migration
    ]

    operations = [
        migrations.RunPython(update_hobby_icons, remove_hobby_icons),
    ]