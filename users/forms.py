from django import forms
from django.contrib.auth.models import User
from .models import Profile

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture', 'major', 'graduation_year', 'phone_number', 'linkedin_url', 'instagram_handle']
        widgets = {
            'graduation_year': forms.NumberInput(attrs={'placeholder': 'e.g., 2025'}),
            'linkedin_url': forms.URLInput(attrs={'placeholder': 'https://linkedin.com/in/yourprofile'}),
            'instagram_handle': forms.TextInput(attrs={'placeholder': 'your_insta_handle'}),
        }