from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django import forms
from django.conf import settings
import uuid
from .models import PasswordResetRequest


class PasswordResetRequestForm(forms.Form):
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your registered email",
            }
        ),
    )


def request_password_reset(request):
    if request.method == "POST":
        form = PasswordResetRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = User.objects.filter(email=email).first()
            if user:
                # Save request to Database so it shows in Admin
                PasswordResetRequest.objects.create(user=user, email=email)

                # Send email to Admin
                subject = f"ACTION REQUIRED: Password Reset Request for {user.username}"
                message = f"User: {user.username}\nEmail: {user.email}\n\nThis user has requested a password reset. Please reset their password in the admin panel and email the new password to them."
                # Sending to a generic admin email or the default from email
                admin_email = getattr(settings, "ADMIN_EMAIL", "admin@u-connect.com")
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [admin_email],
                    fail_silently=True,
                )

            return render(request, "users/password_reset_sent.html")
    else:
        form = PasswordResetRequestForm()

    return render(request, "users/password_reset_request.html", {"form": form})


def guest_chat(request):
    # Assign a unique guest ID if one doesn't exist
    if "guest_id" not in request.session:
        request.session["guest_id"] = str(uuid.uuid4())

    context = {"guest_id": request.session["guest_id"]}
    # In a full implementation, you would load chat history for this guest_id here
    return render(request, "users/guest_chat.html", context)
