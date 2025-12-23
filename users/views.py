from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserUpdateForm, ProfileUpdateForm, CustomUserCreationForm
from business.models import Item

# Create your views here.

@login_required
def home(request):
    # This is the main account dashboard
    active_listings = Item.objects.filter(seller=request.user, status='active').order_by('-created_at')
    sold_history = Item.objects.filter(seller=request.user, status='sold').order_by('-created_at')
    my_purchases = Item.objects.filter(buyer=request.user, status='sold').order_by('-created_at')
    # Ensure profile exists before accessing watchlist
    watchlist_items = request.user.profile.watchlist.all() if hasattr(request.user, 'profile') else []

    context = {
        'active_listings': active_listings,
        'sold_history': sold_history,
        'my_purchases': my_purchases,
        'watchlist_items': watchlist_items,
    }
    return render(request, 'users/home.html', context)

@login_required
def edit_profile(request):
    if hasattr(request.user, 'profile'):
        profile = request.user.profile
    else:
        profile = None

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            new_profile = profile_form.save(commit=False)
            new_profile.user = request.user
            new_profile.save()
            profile_form.save_m2m()
            return redirect('users:home')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    return render(request, 'users/edit_profile.html', context)

def register_user(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('business:home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})

def login_user(request):
    if request.method == 'POST':
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if 'next' in request.POST:
                return redirect(request.POST.get('next'))
            return redirect('business:home')
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})

def logout_user(request):
    if request.method == 'POST':
        logout(request)
        return redirect('users:login')
    return render(request, 'users/logout_confirm.html')