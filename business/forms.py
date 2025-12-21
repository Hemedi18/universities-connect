from django import forms
from .models import Item

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'title', 'category', 'price', 'condition', 'description', 
            'campus_location', 'preferred_meetup', 'contact_method', 
            'contact_email', 'contact_phone', 'image'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }