from django.shortcuts import render, redirect, get_object_or_404
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

def item_detail(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    return render(request, 'business/item_detail.html', {'item': item})

def add_to_cart(request, item_id):
    cart = request.session.get('cart', [])
    if item_id not in cart:
        cart.append(item_id)
        request.session['cart'] = cart
    return redirect('business:view_cart')

def remove_from_cart(request, item_id):
    cart = request.session.get('cart', [])
    if item_id in cart:
        cart.remove(item_id)
        request.session['cart'] = cart
    return redirect('business:view_cart')

def view_cart(request):
    cart = request.session.get('cart', [])
    items = Item.objects.filter(id__in=cart)
    return render(request, 'business/cart.html', {'cart_items': items})

@login_required
def manage_items(request):
    items = Item.objects.filter(seller=request.user).order_by('-created_at')
    return render(request, 'business/manage_items.html', {'items': items})

@login_required
def edit_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.seller != request.user:
        return redirect('business:home')
    
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            return redirect('business:manage_items')
    else:
        form = ItemForm(instance=item)
    return render(request, 'business/post_item.html', {'form': form, 'title': 'Edit Item', 'button_text': 'Update Item'})

@login_required
def delete_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.seller == request.user:
        item.delete()
    return redirect('business:manage_items')