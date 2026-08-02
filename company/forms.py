from django import forms
from .models import Company, Review, Report, District


class CompanyForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["whatsapp_number"].required = True
        self.fields["whatsapp_number"].label = "WhatsApp / Phone"
        self.fields["whatsapp_number"].help_text = (
            "Lazima — buyers watakutafuta hapa."
        )

    def clean_whatsapp_number(self):
        phone = (self.cleaned_data.get("whatsapp_number") or "").strip()
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) < 9:
            raise forms.ValidationError(
                "Weka namba sahihi ya WhatsApp (angalau tarakimu 9)."
            )
        return phone

    class Meta:
        model = Company
        fields = [
            "name",
            "logo",
            "description",
            "region",
            "district",
            "address",
            "instagram_link",
            "whatsapp_number",
            "website_link",
            "opening_time",
            "closing_time",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "logo": forms.FileInput(attrs={"class": "form-control"}),
            "region": forms.Select(attrs={"class": "form-select", "id": "id_region"}),
            "district": forms.Select(
                attrs={"class": "form-select", "id": "id_district"}
            ),
            "address": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Street, Building (e.g. Mlimani City)",
                    "required": False,
                }
            ),
            "instagram_link": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://instagram.com/...",
                }
            ),
            "whatsapp_number": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "255..."}
            ),
            "website_link": forms.URLInput(attrs={"class": "form-control"}),
            "opening_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
            "closing_time": forms.TimeInput(
                attrs={"type": "time", "class": "form-control"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["district"].queryset = District.objects.none()

        if "region" in self.data:
            try:
                region_id = int(self.data.get("region"))
                self.fields["district"].queryset = District.objects.filter(
                    region_id=region_id
                ).order_by("name")
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty queryset
        elif self.instance.pk and self.instance.region:
            self.fields["district"].queryset = self.instance.region.districts.order_by(
                "name"
            )


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "comment"]
        widgets = {
            "rating": forms.HiddenInput(),
            "comment": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "form-control",
                    "placeholder": "Share your experience...",
                }
            ),
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "details"]
        widgets = {
            "reason": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Reason (e.g. Scam, Inappropriate Content)",
                }
            ),
            "details": forms.Textarea(
                attrs={
                    "rows": 4,
                    "class": "form-control",
                    "placeholder": "Please provide more details...",
                }
            ),
        }
