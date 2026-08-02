from django import forms
from .models import Message

# Max upload for chat photos (~2 MB)
CHAT_IMAGE_MAX_BYTES = 2 * 1024 * 1024


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["content", "image"]
        widgets = {
            "content": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Type a message...",
                    "autocomplete": "off",
                    "autofocus": "autofocus",
                }
            ),
            "image": forms.FileInput(
                attrs={
                    "class": "d-none",
                    "id": "chat-image-input",
                    "accept": "image/*",
                }
            ),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            return image
        if getattr(image, "size", 0) > CHAT_IMAGE_MAX_BYTES:
            raise forms.ValidationError("Image must be 2 MB or smaller.")
        content_type = getattr(image, "content_type", "") or ""
        if content_type and not content_type.startswith("image/"):
            raise forms.ValidationError("Only image files are allowed.")
        return image
