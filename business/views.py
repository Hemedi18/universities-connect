from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg
from .forms import ItemForm
from .models import Item, Category, Notification, Comment
import json

# Create your views here.

def home_redirect(request):
    return redirect('customer:home')

def item_detail_redirect(request, item_id):
    return redirect('customer:item_detail', item_id=item_id)

def about_redirect(request):
    return redirect('customer:about')

def contact_redirect(request):
    return redirect('customer:contact')

def documentation_redirect(request):
    return redirect('customer:documentation')

def view_cart_redirect(request):
    return redirect('customer:view_cart')

def add_to_cart_redirect(request, item_id):
    return redirect('customer:add_to_cart', item_id=item_id)

def remove_from_cart_redirect(request, item_id):
    return redirect('customer:remove_from_cart', item_id=item_id)

def view_company_profile_redirect(request, company_id):
    return redirect('company:profile', company_id=company_id)

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
            if hasattr(request.user, 'company_profile'):
                form.instance.company = request.user.company_profile
            form.save() # This calls the custom save method in forms.py which saves attributes
            if hasattr(request.user, 'company_profile'):
                return redirect('company:dashboard')
            else:
                return redirect('business:personal_dashboard')
    else:
        form = ItemForm(category=category)
    return render(request, 'business/post_item.html', {'form': form, 'category': category})

@login_required
def manage_items(request):
    items = Item.objects.filter(seller=request.user).order_by('-created_at')
    return render(request, 'business/manage_items.html', {'items': items})

@login_required
def edit_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.seller != request.user:
        return redirect('customer:home')
    
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

@login_required
def company_dashboard(request):
    try:
        company = request.user.company_profile
    except AttributeError:
        return redirect('company:register')

    items = Item.objects.filter(company=company)
    
    # Overview Stats
    total_products = items.count()
    total_views = items.aggregate(Sum('views'))['views__sum'] or 0
    
    # Reviews & Ratings (Placeholder until Review model is created)
    avg_rating = 0.0
    total_reviews = 0
    recent_reviews = []
    # Uncomment when Review model is available:
    # reviews = Review.objects.filter(item__company=company)
    # avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
    # total_reviews = reviews.count()
    # recent_reviews = reviews.order_by('-created_at')[:5]

    # Charts Data
    # 1. Views per Category
    cat_stats = items.values('category_obj__name').annotate(total_views=Sum('views')).order_by('-total_views')
    category_labels = [stat['category_obj__name'] or 'Uncategorized' for stat in cat_stats]
    category_views = [stat['total_views'] for stat in cat_stats]
    
    # 2. Product Status
    status_stats = items.values('status').annotate(count=Count('id'))
    status_labels = [stat['status'].title() for stat in status_stats]
    status_data = [stat['count'] for stat in status_stats]
    
    # Trending & Suggestions
    trending_items = items.order_by('-views')[:5]
    
    suggestions = []
    low_stock = items.filter(stock_quantity__lt=5, status='active')
    for item in low_stock:
        suggestions.append({
            'item': item,
            'issues': [f'Low stock: {item.stock_quantity} remaining']
        })
        
    recent_comments = Comment.objects.filter(item__company=company).order_by('-created_at')[:5]

    context = {
        'company': company,
        'items': items,
        'total_products': total_products,
        'total_views': total_views,
        'avg_rating': avg_rating,
        'total_reviews': total_reviews,
        'category_labels': json.dumps(category_labels),
        'category_views': json.dumps(category_views),
        'status_labels': json.dumps(status_labels),
        'status_data': json.dumps(status_data),
        'trending_items': trending_items,
        'suggestions': suggestions,
        'recent_reviews': recent_reviews,
        'recent_comments': recent_comments,
    }
    return render(request, 'company/dashboard.html', context)

@login_required
def personal_dashboard(request):
    # Filter items sold by the user (excluding those assigned to a company profile if any, 
    # or just all items by this user if you want a unified view)
    items = Item.objects.filter(seller=request.user).order_by('-created_at')
    
    # Overview Stats
    total_products = items.count()
    total_views = items.aggregate(Sum('views'))['views__sum'] or 0
    
    # Comments on User's Products
    recent_comments = Comment.objects.filter(item__seller=request.user).order_by('-created_at')[:20]
    
    # Graph 1: Views per Category
    views_per_category = items.values('category_obj__name').annotate(total_views=Sum('views')).order_by('-total_views')
    cat_labels = [x['category_obj__name'] or 'Uncategorized' for x in views_per_category]
    cat_data = [x['total_views'] for x in views_per_category]
    
    # Graph 2: Items Status
    status_counts = items.values('status').annotate(count=Count('id'))
    status_labels = [x['status'].title() for x in status_counts]
    status_data = [x['count'] for x in status_counts]

    # Trending (Top Viewed)
    trending_items = items.order_by('-views')[:5]
    
    # Dummy data for spending/orders (until Order model is implemented)
    spending_labels = ['Electronics', 'Food', 'Fashion']
    spending_data = [0, 0, 0]
    recent_orders = []
    
    context = {
        'items': items,
        'total_products': total_products,
        'total_views': total_views,
        'cat_labels': json.dumps(cat_labels),
        'cat_data': json.dumps(cat_data),
        'status_labels': json.dumps(status_labels),
        'status_data': json.dumps(status_data),
        'trending_items': trending_items,
        'recent_comments': recent_comments,
        'spending_labels': json.dumps(spending_labels),
        'spending_data': json.dumps(spending_data),
        'recent_orders': recent_orders,
    }
    
    return render(request, 'business/personal_dashboard.html', context)

@login_required
def notifications_view(request):
    notifications = request.user.notifications.all()
    return render(request, 'business/notifications.html', {'notifications': notifications})

@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect('business:user_notifications')

@login_required
def mark_all_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect('business:user_notifications')

@login_required
def toggle_pin_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.company and item.company.user == request.user:
        item.is_pinned = not item.is_pinned
        item.save()
    return redirect('company:profile', company_id=item.company.id)