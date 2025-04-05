from django.db import models

class Hobby(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.ImageField(upload_to='hobby_icons/', blank=True, null=True)  # Store icons in media/hobby_icons/
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Hobby"
        verbose_name_plural = "Hobbies"