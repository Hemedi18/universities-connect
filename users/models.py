from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(default='profile_pictures/default_profile.jpg', upload_to='profile_pictures')
    major = models.CharField(max_length=100, blank=True, help_text="e.g., Computer Science")
    graduation_year = models.IntegerField(null=True, blank=True, help_text="e.g., 2026")
    is_email_verified = models.BooleanField(default=False, help_text="Indicates if the user has verified their university email.")
    phone_number = models.CharField(max_length=20, blank=True, help_text="Your phone number (kept private).")
    linkedin_url = models.URLField(blank=True, help_text="Link to your LinkedIn profile.")
    instagram_handle = models.CharField(max_length=100, blank=True, help_text="Your Instagram username (without @).")
    watchlist = models.ManyToManyField('business.Item', blank=True, related_name='watched_by')

    def __str__(self):
        return f'{self.user.username} Profile'
