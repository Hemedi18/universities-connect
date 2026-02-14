from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Subquery, OuterRef, F
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string
from business.models import Item, Category, ProductAttributeValue, Comment
from business.forms import CommentForm

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
        return redirect('customer:home')

    items = None
    featured_items = None
    trending_items = None
    recently_viewed = None
    categories = None
    current_category = None
    is_home_feed = False

    # 1. Search
    if query:
        request.session['last_search'] = query
        items = Item.objects.filter(
            Q(title__icontains=query) | 
            Q(description__icontains=query)
        ).select_related('category_obj')
        
        if not items.exists():
            trending_items = Item.objects.filter(status='active').order_by('-views')[:8]
    
    # 2. Category Filter
    elif category_id:
        category = get_object_or_404(Category, id=category_id)
        current_category = category
        children = category.children.all()
        cat_ids = [category.id] + [c.id for c in children]
        items = Item.objects.filter(category_obj_id__in=cat_ids).select_related('category_obj')

        if children.exists():
            categories = children
            for cat in categories:
                cat.icon = 'bi-tag-fill'

    # Browse Mode
    elif browse_mode:
        categories = Category.objects.filter(parent=None)
        # ... (Icon mapping logic can be moved to a utility or kept here)
        return render(request, 'business/home.html', {'categories': categories, 'browse_mode': True})

    # Default Home Feed
    else:
        is_home_feed = True
        categories = Category.objects.filter(parent=None)
        # ... (Icon mapping logic)

        items = Item.objects.filter(status='active')
        
        featured_items = Item.objects.filter(
            status='active',
            is_pinned=True,
            company__is_verified=True
        ).order_by('?')[:8]
        
        trending_items = Item.objects.filter(status='active').order_by('-views')[:8]
        
        viewed_ids = request.session.get('viewed_items', [])
        if viewed_ids:
            recent_ids = viewed_ids[-8:]
            recent_ids.reverse()
            viewed_objs = list(Item.objects.filter(id__in=recent_ids, status='active'))
            viewed_objs.sort(key=lambda x: recent_ids.index(x.id))
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
            items = items.annotate(
                brand_name=Subquery(
                    ProductAttributeValue.objects.filter(
                        product=OuterRef('pk'),
                        attribute__name__in=['Brand', 'Make', 'Provider', 'Publisher', 'Company']
                    ).values('value')[:1]
                )
            ).order_by('brand_name')
        else:
            items = items.order_by('-created_at')

    # Pagination
    if items is not None:
        paginator = Paginator(items, 12)
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

    return render(request, 'business/home.html', {'categories': categories, 'current_category': current_category})

def about(request):
    return render(request, 'business/about.html')

def contact(request):
    return render(request, 'business/contact.html')

def documentation(request):
    return render(request, 'business/documentation.html')

def item_detail(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    
    viewed_items = request.session.get('viewed_items', [])
    if item_id not in viewed_items and request.user != item.seller:
        item.views = F('views') + 1
        item.save(update_fields=['views'])
        item.refresh_from_db()
        viewed_items.append(item_id)
        request.session['viewed_items'] = viewed_items
    
    related_items = Item.objects.filter(
        category_obj=item.category_obj, 
        status='active'
    ).exclude(id=item.id).order_by('?')[:6]
    
    comments = item.comments.all().order_by('-created_at')
    if request.method == 'POST' and request.user.is_authenticated:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.item = item
            comment.user = request.user
            comment.save()
            return redirect('customer:item_detail', item_id=item.id)
    else:
        comment_form = CommentForm()

    return render(request, 'business/item_detail.html', {
        'item': item, 
        'related_items': related_items,
        'comments': comments,
        'comment_form': comment_form
    })

@login_required
def add_to_cart(request, item_id):
    cart = request.session.get('cart', [])
    if item_id not in cart:
        cart.append(item_id)
        request.session['cart'] = cart
    return redirect('customer:view_cart')

@login_required
def remove_from_cart(request, item_id):
    cart = request.session.get('cart', [])
    if item_id in cart:
        cart.remove(item_id)
        request.session['cart'] = cart
    return redirect('customer:view_cart')

@login_required
def view_cart(request):
    cart = request.session.get('cart', [])
    items = Item.objects.filter(id__in=cart)
    return render(request, 'business/cart.html', {'cart_items': items})