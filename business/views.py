from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Subquery, OuterRef
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string
from .forms import ItemForm
from .models import Item, Category, ProductAttributeValue

# Create your views here.

def home(request):
    query = request.GET.get('q')
    category_id = request.GET.get('category')
    browse_mode = request.GET.get('browse')
    page_number = request.GET.get('page', 1)
    sort_by = request.GET.get('sort', 'newest')
    reset = request.GET.get('reset')

    if reset:
        if 'last_search' in request.session:
            del request.session['last_search']
        return redirect('business:home')

    items = None
    categories = None
    current_category = None
    is_home_feed = False

    # 1. Search
    if query:
        # Save search query to session for recommendations
        request.session['last_search'] = query
        # Search functionality
        items = Item.objects.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query)
        ).select_related('category_obj')
    
    # 2. Category Filter
    elif category_id:
        # Filter by Category
        category = get_object_or_404(Category, id=category_id)
        current_category = category
        
        # Check if it has children (Subcategories)
        children = category.children.all()
        
        # Fetch items from this category and its children
        cat_ids = [category.id] + [c.id for c in children]
        items = Item.objects.filter(category_obj_id__in=cat_ids).select_related('category_obj')

        if children.exists():
            categories = children
            # Assign default icon for subcategories
            for cat in categories:
                cat.icon = 'bi-tag-fill'

    # Browse Mode: Show Categories
    elif browse_mode:
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
        return render(request, 'business/home.html', {'categories': categories, 'browse_mode': True})

    # Default Home Feed: Show Recommendations / Items
    else:
        is_home_feed = True
        last_search = request.session.get('last_search')
        # Show all active items by default (as requested: "see all products as normal")
        items = Item.objects.filter(status='active')

    # Apply Sorting
    if items is not None:
        if sort_by == 'price_asc':
            items = items.order_by('price')
        elif sort_by == 'price_desc':
            items = items.order_by('-price')
        elif sort_by == 'oldest':
            items = items.order_by('created_at')
        elif sort_by == 'brand_asc':
            # Sort by Brand/Make attribute
            items = items.annotate(
                brand_name=Subquery(
                    ProductAttributeValue.objects.filter(
                        product=OuterRef('pk'),
                        attribute__name__in=['Brand', 'Make', 'Provider', 'Publisher', 'Company']
                    ).values('value')[:1]
                )
            ).order_by('brand_name')
        else: # newest (default)
            items = items.order_by('-created_at')

    # Pagination Logic (Only if items are present)
    if items is not None:
        paginator = Paginator(items, 12) # 12 items per page
        items_page = paginator.get_page(page_number)

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            html = render_to_string('business/partials/items_list.html', {'items': items_page})
            return JsonResponse({'html': html, 'has_next': items_page.has_next()})

        return render(request, 'business/home.html', {
            'items': items_page, 
            'search_query': query, 
            'current_category': current_category,
            'is_home_feed': is_home_feed,
            'sort_by': sort_by
        })

    # Fallback for categories view
    return render(request, 'business/home.html', {'categories': categories, 'current_category': current_category})

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
        # Assign default icon for subcategories
        for child in children:
            child.icon = 'bi-tag-fill'
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
    
    # Recommendation Logic (Machine Learning / Heuristic)
    # Filter by same category, exclude current item, random order
    related_items = Item.objects.filter(
        category_obj=item.category_obj, 
        status='active'
    ).exclude(id=item.id).order_by('?')[:6]
    return render(request, 'business/item_detail.html', {'item': item, 'related_items': related_items})

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