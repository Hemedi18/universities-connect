from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Profile


def normalize_phone_input(raw):
    return "".join(ch for ch in str(raw or "") if ch.isdigit())


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="Email Address",
        help_text="Lazima — tutakutumia nambari ya OTP kuthibitisha akaunti yako.",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "mfano@email.com",
                "inputmode": "email",
                "autocomplete": "email",
            }
        ),
    )
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
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name not in ["phone_number", "email"]:
                field.help_text = ""
            field.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise forms.ValidationError("Barua pepe (email) ni lazima.")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Barua pepe hii tayari inatumika. Tumia email nyingine au ingia (Login)."
            )
        return email

    def clean_phone_number(self):
        phone = (self.cleaned_data.get("phone_number") or "").strip()
        digits = normalize_phone_input(phone)
        if len(digits) < 9:
            raise forms.ValidationError(
                "Weka namba sahihi ya simu (angalau tarakimu 9)."
            )
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get("email").strip().lower()
        # Inactive until email OTP is verified
        user.is_active = False

        if commit:
            user.save()
            phone = (self.cleaned_data.get("phone_number") or "").strip()
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.phone_number = phone
            profile.is_email_verified = False
            profile.save(update_fields=["phone_number", "is_email_verified"])
        return user


class OTPVerificationForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label="Enter 6-digit OTP Code",
        widget=forms.TextInput(
            attrs={
                "class": "form-control text-center fs-3 fw-bold tracking-widest",
                "placeholder": "123456",
                "maxlength": "6",
                "inputmode": "numeric",
                "pattern": "[0-9]*",
                "autocomplete": "one-time-code",
                "autofocus": "autofocus",
            }
        ),
    )

    def clean_otp_code(self):
        code = self.cleaned_data.get("otp_code", "").strip()
        if not code.isdigit() or len(code) != 6:
            raise forms.ValidationError("Weka nambari ya OTP yenye tarakimu 6 (nambari pekee).")
        return code


class PasswordResetOTPRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Weka email yako uliyojisajili nayo",
                "autocomplete": "email",
            }
        ),
    )


class PasswordResetWithOTPForm(forms.Form):
    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label="6-Digit Reset Code",
        widget=forms.TextInput(
            attrs={
                "class": "form-control text-center fs-4 fw-bold",
                "placeholder": "123456",
                "maxlength": "6",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
            }
        ),
    )
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Nenosiri jipya (angalau herufi 6)",
                "autocomplete": "new-password",
            }
        ),
        min_length=6,
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Rudia nenosiri jipya",
                "autocomplete": "new-password",
            }
        ),
        min_length=6,
    )

    def clean(self):
        cleaned_data = super().clean()
        pw = cleaned_data.get("new_password")
        confirm = cleaned_data.get("confirm_password")
        if pw and confirm and pw != confirm:
            raise forms.ValidationError("Nenosiri ulizoingiza hazilingani. Kagua tena.")
        return cleaned_data



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
