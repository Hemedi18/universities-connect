from django import forms

from .models import Order, OrderItem


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=255, label="Full name")
    phone = forms.CharField(max_length=30, label="Phone number")
    email = forms.EmailField(required=False, label="Email")
    fulfillment_method = forms.ChoiceField(
        choices=Order.FULFILLMENT_CHOICES,
        widget=forms.RadioSelect,
        initial=Order.FULFILLMENT_PICKUP,
        label="Fulfillment",
    )
    campus_location = forms.CharField(
        max_length=255,
        required=False,
        label="Campus / meetup location",
        help_text="Required for campus pickup.",
    )
    address_line = forms.CharField(
        max_length=255,
        required=False,
        label="Delivery address",
        help_text="Required for delivery.",
    )
    payment_method = forms.ChoiceField(
        choices=[(Order.PAY_COD, "Cash on Delivery")],
        widget=forms.HiddenInput,
        initial=Order.PAY_COD,
        label="Payment method",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Order notes",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name in ("fulfillment_method", "payment_method", "notes"):
                continue
            css = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{css} form-control".strip()
        self.fields["notes"].widget.attrs["class"] = "form-control"
        self.fields["payment_method"].initial = Order.PAY_COD
        if user is not None:
            self.fields["full_name"].initial = user.get_full_name() or user.username
            self.fields["email"].initial = user.email or ""
            profile = getattr(user, "profile", None)
            if profile and profile.phone_number:
                self.fields["phone"].initial = profile.phone_number

    def clean(self):
        cleaned = super().clean()
        fulfillment = cleaned.get("fulfillment_method")
        cleaned["payment_method"] = Order.PAY_COD
        if fulfillment == Order.FULFILLMENT_PICKUP and not cleaned.get(
            "campus_location"
        ):
            self.add_error("campus_location", "Enter a campus or meetup location.")
        if fulfillment == Order.FULFILLMENT_DELIVERY and not cleaned.get(
            "address_line"
        ):
            self.add_error("address_line", "Enter a delivery address.")
        return cleaned


class PaymentReferenceForm(forms.Form):
    payment_reference = forms.CharField(
        max_length=100,
        label="Transaction / payment reference",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


class SellerFulfillmentForm(forms.Form):
    fulfillment_status = forms.ChoiceField(
        choices=OrderItem.FULFILLMENT_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
