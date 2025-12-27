from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Subquery, OuterRef, Avg, F, Count, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string
from .forms import ItemForm, CompanyForm, ReviewForm, ReportForm, CommentForm
from .models import Item, Category, ProductAttributeValue, Company, Notification, Review, Report, Comment

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
    featured_items = None
    trending_items = None
    recently_viewed = None
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
        
        # Featured Items (Pinned items from verified companies)
        featured_items = Item.objects.filter(
            status='active',
            is_pinned=True,
            company__is_verified=True
        ).order_by('?')[:8]
        
        # Trending Items (Most viewed)
        trending_items = Item.objects.filter(status='active').order_by('-views')[:8]
        
        # Recently Viewed Items (From Session)
        viewed_ids = request.session.get('viewed_items', [])
        if viewed_ids:
            recent_ids = viewed_ids[-8:] # Get last 8 viewed
            recent_ids.reverse() # Show most recent first
            viewed_objs = list(Item.objects.filter(id__in=recent_ids, status='active'))
            viewed_objs.sort(key=lambda x: recent_ids.index(x.id)) # Sort by order in session
            recently_viewed = viewed_objs

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
            'sort_by': sort_by,
            'featured_items': featured_items,
            'trending_items': trending_items,
            'recently_viewed': recently_viewed
        })

    # Fallback for categories view
    return render(request, 'business/home.html', {'categories': categories, 'current_category': current_category})

def about(request):
    return render(request, 'business/about.html')

def contact(request):
    return render(request, 'business/contact.html')

def documentation(request):
    return render(request, 'business/documentation.html')

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
            return redirect('business:home')
    else:
        form = ItemForm(category=category)
    return render(request, 'business/post_item.html', {'form': form, 'category': category})

def item_detail(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    
    # Track unique views using session to prevent spamming
    viewed_items = request.session.get('viewed_items', [])

    if item_id not in viewed_items and request.user != item.seller:
        item.views = F('views') + 1
        item.save(update_fields=['views'])
        item.refresh_from_db()
        viewed_items.append(item_id)
        request.session['viewed_items'] = viewed_items
    
    # Recommendation Logic (Machine Learning / Heuristic)
    # Filter by same category, exclude current item, random order
    related_items = Item.objects.filter(
        category_obj=item.category_obj, 
        status='active'
    ).exclude(id=item.id).order_by('?')[:6]
    
    # Comments Logic
    comments = item.comments.all().order_by('-created_at')
    if request.method == 'POST' and request.user.is_authenticated:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.item = item
            comment.user = request.user
            comment.save()
            return redirect('business:item_detail', item_id=item.id)
    else:
        comment_form = CommentForm()

    return render(request, 'business/item_detail.html', {
        'item': item, 
        'related_items': related_items,
        'comments': comments,
        'comment_form': comment_form
    })

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

@login_required
def company_dashboard(request):
    # Check if user has a company profile
    if not hasattr(request.user, 'company_profile'):
        return redirect('business:home')
    
    company = request.user.company_profile
    
    # Date Filtering
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    items = Item.objects.filter(company=company).order_by('-created_at')
    
    if start_date_str:
        items = items.filter(created_at__date__gte=start_date_str)
    if end_date_str:
        items = items.filter(created_at__date__lte=end_date_str)

    # Filter reviews based on date range as well if needed, or keep them global

    # Overview Stats
    total_products = items.count()
    total_views = items.aggregate(Sum('views'))['views__sum'] or 0
    total_reviews = company.reviews.count()
    avg_rating = company.reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
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
    
    # Recent Reviews
    recent_reviews = company.reviews.all().order_by('-created_at')[:5]

    # Recent Comments on Company Products
    recent_comments = Comment.objects.filter(item__company=company).order_by('-created_at')[:20]
    
    # Suggestions Logic
    suggestions = []
    for item in items:
        issues = []
        if not item.image:
            issues.append("Missing main image")
        if len(item.description) < 50:
            issues.append("Description is too short")
        if item.views < 10 and (timezone.now() - item.created_at).days > 7:
            issues.append("Low visibility - Consider sharing")
        if item.stock_quantity < 3:
            issues.append("Low stock warning")
            
        if issues:
            suggestions.append({
                'item': item,
                'issues': issues
            })
    
    context = {
        'company': company,
        'items': items,
        'total_products': total_products,
        'total_views': total_views,
        'total_reviews': total_reviews,
        'avg_rating': avg_rating,
        'cat_labels': cat_labels,
        'cat_data': cat_data,
        'status_labels': status_labels,
        'status_data': status_data,
        'trending_items': trending_items,
        'recent_reviews': recent_reviews,
        'recent_comments': recent_comments,
        'suggestions': suggestions[:5],
        'start_date': start_date_str,
        'end_date': end_date_str,
    }
    
    return render(request, 'business/company_dashboard.html', context)

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
    
    context = {
        'items': items,
        'total_products': total_products,
        'total_views': total_views,
        'cat_labels': cat_labels,
        'cat_data': cat_data,
        'status_labels': status_labels,
        'status_data': status_data,
        'trending_items': trending_items,
        'recent_comments': recent_comments,
    }
    
    return render(request, 'business/personal_dashboard.html', context)

@login_required
def edit_company_profile(request):
    if not hasattr(request.user, 'company_profile'):
        return redirect('business:home')
    
    company = request.user.company_profile
    
    if request.method == 'POST':
        form = CompanyForm(request.POST, request.FILES, instance=company)
        if form.is_valid():
            form.save()
            return redirect('business:company_dashboard')
    else:
        form = CompanyForm(instance=company)
    
    return render(request, 'business/edit_company_profile.html', {'form': form})

def view_company_profile(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    items_qs = Item.objects.filter(company=company, status='active').order_by('-is_pinned', '-created_at')

    query = request.GET.get('q')
    if query:
        items_qs = items_qs.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query)
        )
    
    paginator = Paginator(items_qs, 12) # Show 12 items per page
    page_number = request.GET.get('page')
    items = paginator.get_page(page_number)

    is_following = False
    if request.user.is_authenticated:
        is_following = request.user in company.followers.all()

    # Review Sorting
    review_sort = request.GET.get('review_sort', 'newest')
    reviews = company.reviews.all()
    
    if review_sort == 'oldest':
        reviews = reviews.order_by('created_at')
    elif review_sort == 'highest':
        reviews = reviews.order_by('-rating')
    elif review_sort == 'lowest':
        reviews = reviews.order_by('rating')
    else: # newest
        reviews = reviews.order_by('-created_at')

    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg']
    review_form = ReviewForm()
    
    return render(request, 'business/company_profile.html', {'company': company, 'items': items, 'is_following': is_following, 'reviews': reviews, 'avg_rating': avg_rating, 'review_form': review_form, 'review_sort': review_sort})

@login_required
def toggle_follow_company(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    if request.user in company.followers.all():
        company.followers.remove(request.user)
    else:
        company.followers.add(request.user)
    return redirect('business:view_company_profile', company_id=company_id)

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
def add_review(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.company = company
            review.user = request.user
            review.save()
    return redirect('business:view_company_profile', company_id=company_id)

@login_required
def edit_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id)
    if review.user != request.user:
        return redirect('business:view_company_profile', company_id=review.company.id)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            form.save()
            return redirect('business:view_company_profile', company_id=review.company.id)
    else:
        form = ReviewForm(instance=review)
    
    return render(request, 'business/edit_review.html', {'form': form, 'company': review.company})

@login_required
def delete_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id)
    company_id = review.company.id
    if review.user == request.user:
        review.delete()
    return redirect('business:view_company_profile', company_id=company_id)

@login_required
def report_company(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    if request.method == 'POST':
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.company = company
            report.user = request.user
            report.save()
            return redirect('business:view_company_profile', company_id=company_id)
    else:
        form = ReportForm()
    return render(request, 'business/report_company.html', {'form': form, 'company': company})

@login_required
def toggle_pin_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.company and item.company.user == request.user:
        item.is_pinned = not item.is_pinned
        item.save()
    return redirect('business:view_company_profile', company_id=item.company.id)