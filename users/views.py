from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserUpdateForm, ProfileUpdateForm, CustomUserCreationForm
from business.models import Item
from customer.models import Order

# Create your views here.


@login_required
def home(request):
    # This is the main account dashboard
    active_listings = Item.objects.filter(
        seller=request.user, status="active"
    ).order_by("-created_at")
    sold_history = Item.objects.filter(seller=request.user, status="sold").order_by(
        "-created_at"
    )
    my_orders = Order.objects.filter(buyer=request.user).prefetch_related("items")[:10]
    my_purchases = Item.objects.filter(buyer=request.user).order_by("-created_at")[:10]
    # Ensure profile exists before accessing watchlist
    watchlist_items = (
        request.user.profile.watchlist.all() if hasattr(request.user, "profile") else []
    )

    context = {
        "active_listings": active_listings,
        "sold_history": sold_history,
        "my_orders": my_orders,
        "my_purchases": my_purchases,
        "watchlist_items": watchlist_items,
    }
    return render(request, "users/home.html", context)


@login_required
def edit_profile(request):
    if hasattr(request.user, "profile"):
        profile = request.user.profile
    else:
        profile = None

    if request.method == "POST":
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            new_profile = profile_form.save(commit=False)
            new_profile.user = request.user
            new_profile.save()
            profile_form.save_m2m()
            # Keep listings in sync so buyers always see the new number
            phone = (new_profile.phone_number or "").strip()
            updated = Item.objects.filter(seller=request.user).update(
                contact_phone=phone
            )
            messages.success(
                request,
                f"Profile updated. Contact synced to {updated} listing(s).",
            )
            return redirect("users:home")
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    context = {
        "user_form": user_form,
        "profile_form": profile_form,
    }
    return render(request, "users/edit_profile.html", context)


from .forms import (
    UserUpdateForm,
    ProfileUpdateForm,
    CustomUserCreationForm,
    OTPVerificationForm,
)
from .models import EmailOTP, Profile
from .utils_otp import send_otp_email
from django.shortcuts import get_object_or_404


def register_user(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Generate and send 6-digit OTP to the registered email
            otp = EmailOTP.create_otp(
                email=user.email, purpose="registration", user=user
            )
            send_otp_email(
                email=user.email,
                otp_code=otp.otp_code,
                purpose="registration",
                username=user.username,
            )

            # Store in session for the verification page
            request.session["otp_verify_user_id"] = user.id
            request.session["otp_verify_email"] = user.email

            messages.info(
                request,
                f"Tumekutumia nambari ya OTP kwenye barua pepe {user.email}. Tafadhali weka hapa kuthibitisha.",
            )
            return redirect("users:verify_otp")
    else:
        form = CustomUserCreationForm()
    return render(request, "users/register.html", {"form": form})


def verify_registration_otp(request):
    user_id = request.session.get("otp_verify_user_id")
    email = request.session.get("otp_verify_email")

    if not user_id or not email:
        messages.warning(request, "Tafadhali jisajili kwanza.")
        return redirect("users:register")

    user = get_object_or_404(User, id=user_id)

    if request.method == "POST":
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["otp_code"]
            otp = EmailOTP.objects.filter(
                email__iexact=email, purpose="registration", is_used=False
            ).first()

            if not otp:
                form.add_error("otp_code", "Hakuna OTP iliyo hai. Tafadhali bonyeza 'Tuma tena OTP'.")
            else:
                ok, msg = otp.verify(code)
                if ok:
                    # Activate user and verify profile
                    user.is_active = True
                    user.save(update_fields=["is_active"])
                    profile, _ = Profile.objects.get_or_create(user=user)
                    profile.is_email_verified = True
                    profile.save(update_fields=["is_email_verified"])

                    # Clear session
                    request.session.pop("otp_verify_user_id", None)
                    request.session.pop("otp_verify_email", None)

                    # Auto login
                    login(request, user)
                    messages.success(
                        request,
                        f"Hongera {user.username}! Barua pepe yako imethibitishwa kikamilifu.",
                    )
                    return redirect("customer:home")
                else:
                    form.add_error("otp_code", msg)
    else:
        form = OTPVerificationForm()

    context = {
        "form": form,
        "email": email,
        "username": user.username,
    }
    return render(request, "users/verify_otp.html", context)


def resend_registration_otp(request):
    user_id = request.session.get("otp_verify_user_id")
    email = request.session.get("otp_verify_email")

    if not user_id or not email:
        messages.warning(request, "Kipindi chako kimemalizika. Tafadhali jisajili tena.")
        return redirect("users:register")

    user = get_object_or_404(User, id=user_id)

    # Generate new OTP and send
    otp = EmailOTP.create_otp(email=email, purpose="registration", user=user)
    send_otp_email(
        email=email,
        otp_code=otp.otp_code,
        purpose="registration",
        username=user.username,
    )
    messages.success(
        request, f"Nambari mpya ya OTP imetumwa kwenye barua pepe {email}."
    )
    return redirect("users:verify_otp")


def login_user(request):
    if request.method == "POST":
        raw_username = request.POST.get("username", "").strip()
        raw_password = request.POST.get("password", "")

        # Look up candidate by username or email
        candidate = (
            User.objects.filter(username__iexact=raw_username).first()
            or User.objects.filter(email__iexact=raw_username).first()
        )

        # 1. Check if user entered valid credentials but account is pending OTP verification
        if candidate and not candidate.is_active and candidate.check_password(raw_password):
            otp = EmailOTP.create_otp(
                email=candidate.email, purpose="registration", user=candidate
            )
            send_otp_email(
                email=candidate.email,
                otp_code=otp.otp_code,
                purpose="registration",
                username=candidate.username,
            )
            request.session["otp_verify_user_id"] = candidate.id
            request.session["otp_verify_email"] = candidate.email
            messages.warning(
                request,
                f"Akaunti yako bado haijathibitishwa. Tumekutumia nambari mpya ya OTP kwenye {candidate.email}.",
            )
            return redirect("users:verify_otp")

        # 2. Support logging in with email or username seamlessly
        post_data = request.POST.copy()
        if candidate and candidate.is_active and candidate.check_password(raw_password):
            post_data["username"] = candidate.username

        form = AuthenticationForm(data=post_data)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Karibu tena, {user.username}!")
            if "next" in request.POST:
                return redirect(request.POST.get("next"))

            # Redirect business users to dashboard, others to home
            if hasattr(user, "company_profile"):
                return redirect("company:dashboard")
            return redirect("customer:home")
        else:
            messages.error(
                request,
                "Imeshindwa kuingia! Jina la mtumiaji au nenosiri si sahihi. Kagua tena au bofya 'Umesahau nenosiri?' kurejesha akaunti yako."
            )
    else:
        form = AuthenticationForm()

    return render(request, "users/login.html", {"form": form})



def logout_user(request):
    if request.method == "POST":
        logout(request)
        return redirect("users:login")
    return render(request, "users/logout_confirm.html")
