# Generated by Django 5.2 on 2025-04-11 14:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('signup', '0006_customuser_profile_pic_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='two_factor_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
