from django import forms
from .models import Message

class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['content', 'image']
        widgets = {
            'content': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Type a message...',
                'autocomplete': 'off',
                'autofocus': 'autofocus'
            }),
            'image': forms.FileInput(attrs={'class': 'd-none', 'id': 'chat-image-input'}),
        }