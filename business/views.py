from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .forms import ItemForm
from .models import Item, Category

# Create your views here.

def home(request):
    query = request.GET.get('q')
    category_id = request.GET.get('category')

    if query:
        # Search functionality
        items = Item.objects.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query)
        ).select_related('category_obj').order_by('-created_at')
        return render(request, 'business/home.html', {'items': items, 'search_query': query})
    
    if category_id:
        # Filter by Category
        category = get_object_or_404(Category, id=category_id)
        
        # Check if it has children (Subcategories)
        children = category.children.all()
        if children.exists():
            # Show subcategories instead of items
            return render(request, 'business/home.html', {'categories': children, 'current_category': category})
        
        # Leaf category: Show items
        items = Item.objects.filter(category_obj=category).select_related('category_obj').order_by('-created_at')
        return render(request, 'business/home.html', {'items': items, 'current_category': category})

    # Default: Show Categories
    categories = Category.objects.filter(parent=None)
    icon_mapping = {
        'Electronics': 'bi-laptop',
        'Transportation': 'bi-car-front-fill',
        'Food & Beverages': 'bi-basket2-fill',
        'Fashion': 'bi-bag-heart-fill',
        'Home & Kitchen': 'bi-house-door-fill',
        'Health & Beauty': 'bi-heart-pulse-fill',
        'Real Estate': 'bi-buildings-fill',
        'Industrial': 'bi-tools',
        'Media & Books': 'bi-book-half',
        'Services': 'bi-people-fill',
        'Others': 'bi-grid-fill',
    }
    for cat in categories:
        cat.icon = icon_mapping.get(cat.name, 'bi-tag-fill')

    return render(request, 'business/home.html', {'categories': categories})

def about(request):
    return render(request, 'business/about.html')

def contact(request):
    return render(request, 'business/contact.html')

@login_required
def post_item(request):
    # Step 1: Check if category is selected
    category_id = request.GET.get('category')
    if not category_id:
        # Show top-level categories
        categories = Category.objects.filter(parent=None)
        
        # Assign icons based on category name
        icon_mapping = {
            'Electronics': 'bi-laptop',
            'Transportation': 'bi-car-front-fill',
            'Food & Beverages': 'bi-basket2-fill',
            'Fashion': 'bi-bag-heart-fill',
            'Home & Kitchen': 'bi-house-door-fill',
            'Health & Beauty': 'bi-heart-pulse-fill',
            'Real Estate': 'bi-buildings-fill',
            'Industrial': 'bi-tools',
            'Media & Books': 'bi-book-half',
            'Services': 'bi-people-fill',
            'Others': 'bi-grid-fill',
        }
        for cat in categories:
            cat.icon = icon_mapping.get(cat.name, 'bi-tag-fill')
            
        return render(request, 'business/select_category.html', {'categories': categories})

    category = get_object_or_404(Category, id=category_id)
    
    # Check for subcategories
    children = category.children.all()
    if children.exists():
        # Render selection for subcategories
        return render(request, 'business/select_category.html', {'categories': children, 'parent_category': category})

    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES, category=category)
        if form.is_valid():
            form.instance.seller = request.user
            form.save() # This calls the custom save method in forms.py which saves attributes
            return redirect('business:home')
    else:
        form = ItemForm(category=category)
    return render(request, 'business/post_item.html', {'form': form, 'category': category})

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