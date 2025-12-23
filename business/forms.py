from django import forms
from .models import Item

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'title',
            'category',
            'price',
            'condition',
            'description',
            'contact_method',
            'contact_email',
            'contact_phone',
            'image',
            'image2',
            'image3',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }