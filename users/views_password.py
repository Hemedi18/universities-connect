from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.contrib import messages
from .models import PasswordResetRequest, EmailOTP
from .forms import PasswordResetOTPRequestForm, PasswordResetWithOTPForm
from .utils_otp import send_otp_email


def request_password_reset(request):
    if request.method == "POST":
        form = PasswordResetOTPRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].strip().lower()
            user = User.objects.filter(email__iexact=email).first()
            if user:
                # 1. Generate & send 6-digit OTP code to the user's email
                otp = EmailOTP.create_otp(
                    email=user.email, purpose="password_reset", user=user
                )
                send_otp_email(
                    email=user.email,
                    otp_code=otp.otp_code,
                    purpose="password_reset",
                    username=user.username,
                )

                # 2. Record request for admin audit
                PasswordResetRequest.objects.create(user=user, email=email)

                # 3. Store email in session and redirect to verify screen
                request.session["password_reset_email"] = user.email
                messages.info(
                    request,
                    f"Tumekutumia nambari ya OTP yenye tarakimu 6 kwenye barua pepe {user.email}.",
                )
                return redirect("password_reset_verify")
            else:
                form.add_error(
                    "email",
                    "Hakuna akaunti iliyopatikana yenye barua pepe hii. Kagua tena au tumia Support Chat.",
                )
    else:
        form = PasswordResetOTPRequestForm()

    return render(request, "users/password_reset_request.html", {"form": form})


def verify_password_reset(request):
    email = request.session.get("password_reset_email")
    if not email:
        messages.warning(request, "Tafadhali anza kwa kuweka barua pepe yako.")
        return redirect("password_reset_request")

    user = get_object_or_404(User, email__iexact=email)

    if request.method == "POST":
        form = PasswordResetWithOTPForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["otp_code"]
            otp = EmailOTP.objects.filter(
                email__iexact=email, purpose="password_reset", is_used=False
            ).first()

            if not otp:
                form.add_error("otp_code", "Hakuna OTP iliyo hai. Tafadhali bonyeza 'Tuma tena OTP'.")
            else:
                ok, msg = otp.verify(code)
                if ok:
                    # Update password
                    user.set_password(form.cleaned_data["new_password"])
                    user.is_active = True
                    user.save(update_fields=["password", "is_active"])

                    # Clear session
                    request.session.pop("password_reset_email", None)

                    messages.success(
                        request,
                        "Nenosiri jipya limewekwa kikamilifu! Sasa unaweza kuingia kwa kutumia nenosiri lako jipya.",
                    )
                    return redirect("users:login")
                else:
                    form.add_error("otp_code", msg)
    else:
        form = PasswordResetWithOTPForm()

    context = {
        "form": form,
        "email": email,
        "username": user.username,
    }
    return render(request, "users/password_reset_verify.html", context)


def resend_password_reset_otp(request):
    email = request.session.get("password_reset_email")
    if not email:
        messages.warning(request, "Kipindi chako kimemalizika. Weka tena email yako.")
        return redirect("password_reset_request")

    user = get_object_or_404(User, email__iexact=email)
    otp = EmailOTP.create_otp(email=email, purpose="password_reset", user=user)
    send_otp_email(
        email=email,
        otp_code=otp.otp_code,
        purpose="password_reset",
        username=user.username,
    )
    messages.success(
        request, f"Nambari mpya ya OTP ya kubadilisha password imetumwa kwenye {email}."
    )
    return redirect("password_reset_verify")


from .views_support import guest_chat


