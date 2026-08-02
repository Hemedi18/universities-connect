from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile


def normalize_phone_input(raw):
    return "".join(ch for ch in str(raw or "") if ch.isdigit())


class CustomUserCreationForm(UserCreationForm):
    phone_number = forms.CharField(
        max_length=20,
        required=True,
        label="Phone / WhatsApp",
        help_text="Lazima — buyers watakutafuta hapa (mf. 0712345678).",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "0712345678",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        ),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = UserCreationForm.Meta.fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != "phone_number":
                field.help_text = ""
            field.widget.attrs.setdefault("class", "form-control")

    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        digits = normalize_phone_input(phone)
        if len(digits) < 9:
            raise forms.ValidationError(
                "Weka namba sahihi ya simu (angalau tarakimu 9)."
            )
        return phone

    def save(self, commit=True):
        user = super().save(commit=commit)
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        if commit:
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone_number = phone
            profile.save(update_fields=["phone_number"])
        return user


class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "set-input")


class ProfileUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_number"].required = True
        self.fields["phone_number"].label = "Phone / WhatsApp"
        self.fields["phone_number"].help_text = (
            "Lazima — inahitajika ukiuza (Cash on Delivery / WhatsApp)."
        )
        self.fields["phone_number"].widget.attrs.update(
            {
                "placeholder": "0712345678",
                "inputmode": "tel",
                "autocomplete": "tel",
            }
        )
        for name, field in self.fields.items():
            if name != "profile_picture":
                field.widget.attrs.setdefault("class", "set-input")
            else:
                field.widget.attrs.setdefault("class", "fu-input set-file")
                field.widget.attrs.setdefault("accept", "image/*")


    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        digits = normalize_phone_input(phone)
        if len(digits) < 9:
            raise forms.ValidationError(
                "Weka namba sahihi ya simu (angalau tarakimu 9)."
            )
        return phone

    class Meta:
        model = Profile
        fields = [
            "profile_picture",
            "major",
            "graduation_year",
            "phone_number",
            "linkedin_url",
            "instagram_handle",
        ]
        widgets = {
            "profile_picture": forms.FileInput(
                attrs={"class": "fu-input set-file", "accept": "image/*", "id": "id_profile_picture"}
            ),
            "graduation_year": forms.NumberInput(attrs={"placeholder": "e.g., 2025"}),
            "linkedin_url": forms.URLInput(
                attrs={"placeholder": "https://linkedin.com/in/yourprofile"}
            ),
            "instagram_handle": forms.TextInput(
                attrs={"placeholder": "your_insta_handle"}
            ),
        }
