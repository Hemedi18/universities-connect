from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import ItemForm
from .models import Item

# Create your views here.

def home(request):
    items = Item.objects.all().order_by('-created_at')
    return render(request, 'business/home.html', {'items': items})

def about(request):
    return render(request, 'business/about.html')

def contact(request):
    return render(request, 'business/contact.html')

@login_required
def post_item(request):
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.seller = request.user
            item.save()
            return redirect('business:home')
    else:
        form = ItemForm()
    return render(request, 'business/post_item.html', {'form': form})