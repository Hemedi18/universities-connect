from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, Avg
from django.views.decorators.http import require_POST
from .forms import ItemForm, MAX_ITEM_MEDIA, save_item_media_files, validate_uploaded_media
from .models import Item, ItemMedia, Category, Notification, Comment
import json

# Create your views here.


def home_redirect(request):
    return redirect("customer:home")


def item_detail_redirect(request, item_id):
    return redirect("customer:item_detail", item_id=item_id)


def about_redirect(request):
    return redirect("customer:about")


def contact_redirect(request):
    return redirect("customer:contact")


def documentation_redirect(request):
    return redirect("customer:documentation")


def view_cart_redirect(request):
    return redirect("customer:view_cart")


def add_to_cart_redirect(request, item_id):
    return redirect("customer:add_to_cart", item_id=item_id)


def remove_from_cart_redirect(request, item_id):
    return redirect("customer:remove_from_cart", item_id=item_id)


def view_company_profile_redirect(request, company_id):
    return redirect("company:profile", company_id=company_id)


def _process_item_media(request, item, *, require_image=False):
    """Handle remove_media_ids + media_files uploads. Returns error message or None."""
    remove_ids = request.POST.getlist("remove_media_ids")
    if remove_ids:
        ItemMedia.objects.filter(item=item, id__in=remove_ids).delete()
        # Re-sequence
        for i, media in enumerate(item.media.order_by("sort_order", "id")):
            if media.sort_order != i:
                media.sort_order = i
                media.save(update_fields=["sort_order"])

    uploads = request.FILES.getlist("media_files")
    existing = item.media.count()
    if existing + len(uploads) > MAX_ITEM_MEDIA:
        return f"Maximum {MAX_ITEM_MEDIA} photos/videos per item."

    try:
        for uploaded in uploads:
            validate_uploaded_media(uploaded)
        if uploads:
            save_item_media_files(item, uploads, start_order=existing)
        else:
            item.sync_legacy_media_fields()
    except ValidationError as exc:
        return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)

    has_image = item.media.filter(media_type=ItemMedia.MEDIA_IMAGE).exists() or bool(
        item.image
    )
    if require_image and not has_image:
        return "Add at least one product photo."
    return None


@login_required
def post_item(request):
    # Sellers must have a contact phone before listing
    profile = getattr(request.user, "profile", None)
    phone = (getattr(profile, "phone_number", None) or "").strip()
    if not phone:
        messages.warning(
            request,
            "Ongeza namba yako ya simu / WhatsApp kwenye profile kabla ya kuuza.",
        )
        return redirect("users:edit_profile")

    # Step 1: Check if category is selected
    category_id = request.GET.get("category")
    if not category_id:
        # Show top-level categories
        categories = Category.objects.filter(parent=None)

        # Assign icons based on category name
        icon_mapping = {
            "Electronics": "bi-laptop",
            "Transportation": "bi-car-front-fill",
            "Food & Beverages": "bi-basket2-fill",
            "Fashion": "bi-bag-heart-fill",
            "Home & Kitchen": "bi-house-door-fill",
            "Health & Beauty": "bi-heart-pulse-fill",
            "Real Estate": "bi-buildings-fill",
            "Industrial": "bi-tools",
            "Media & Books": "bi-book-half",
            "Services": "bi-people-fill",
            "Others": "bi-grid-fill",
        }
        for cat in categories:
            cat.icon = icon_mapping.get(cat.name, "bi-tag-fill")

        return render(
            request, "business/select_category.html", {"categories": categories}
        )

    category = get_object_or_404(Category, id=category_id)

    # Check for subcategories
    children = category.children.all()
    if children.exists():
        # Assign default icon for subcategories
        for child in children:
            child.icon = "bi-tag-fill"
        # Render selection for subcategories
        return render(
            request,
            "business/select_category.html",
            {"categories": children, "parent_category": category},
        )

    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, category=category)
        if form.is_valid():
            form.instance.seller = request.user
            if hasattr(request.user, "company_profile"):
                form.instance.company = request.user.company_profile
            # Prefer live profile/company phone on new listings
            if not (form.instance.contact_phone or "").strip():
                form.instance.contact_phone = phone
            item = form.save()
            err = _process_item_media(request, item, require_image=True)
            if err:
                item.delete()
                messages.error(request, err)
            else:
                messages.success(request, "Item posted successfully.")
                if hasattr(request.user, "company_profile"):
                    return redirect("company:dashboard")
                return redirect("business:personal_dashboard")
    else:
        form = ItemForm(category=category)
    return render(
        request,
        "business/post_item.html",
        {
            "form": form,
            "category": category,
            "existing_media": [],
            "max_media": MAX_ITEM_MEDIA,
        },
    )


@login_required
def manage_items(request):
    items = Item.objects.filter(seller=request.user).order_by("-created_at")
    return render(request, "business/manage_items.html", {"items": items})


@login_required
def edit_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.seller != request.user:
        return redirect("customer:home")

    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            err = _process_item_media(request, item, require_image=True)
            if err:
                messages.error(request, err)
            else:
                messages.success(request, "Item updated.")
                return redirect("business:manage_items")
    else:
        form = ItemForm(instance=item)
    return render(
        request,
        "business/post_item.html",
        {
            "form": form,
            "title": "Edit Item",
            "button_text": "Update Item",
            "existing_media": list(item.media.all()),
            "max_media": MAX_ITEM_MEDIA,
            "item": item,
        },
    )


@login_required
@require_POST
def delete_item_media(request, media_id):
    media = get_object_or_404(ItemMedia, pk=media_id)
    item = media.item
    if item.seller_id != request.user.id:
        return redirect("customer:home")
    media.delete()
    for i, row in enumerate(item.media.order_by("sort_order", "id")):
        if row.sort_order != i:
            row.sort_order = i
            row.save(update_fields=["sort_order"])
    item.sync_legacy_media_fields()
    messages.info(request, "Media removed.")
    return redirect("business:edit_item", item_id=item.id)


@login_required
def delete_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.seller == request.user:
        item.delete()
    return redirect("business:manage_items")


@login_required
def company_dashboard(request):
    try:
        company = request.user.company_profile
    except AttributeError:
        return redirect("company:register")

    items = Item.objects.filter(company=company)

    # Overview Stats
    total_products = items.count()
    total_views = items.aggregate(Sum("views"))["views__sum"] or 0

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
    cat_stats = (
        items.values("category_obj__name")
        .annotate(total_views=Sum("views"))
        .order_by("-total_views")
    )
    category_labels = [
        stat["category_obj__name"] or "Uncategorized" for stat in cat_stats
    ]
    category_views = [stat["total_views"] for stat in cat_stats]

    # 2. Product Status
    status_stats = items.values("status").annotate(count=Count("id"))
    status_labels = [stat["status"].title() for stat in status_stats]
    status_data = [stat["count"] for stat in status_stats]

    # Trending & Suggestions
    trending_items = items.order_by("-views")[:5]

    suggestions = []
    low_stock = items.filter(stock_quantity__lt=5, status="active")
    for item in low_stock:
        suggestions.append(
            {"item": item, "issues": [f"Low stock: {item.stock_quantity} remaining"]}
        )

    recent_comments = Comment.objects.filter(item__company=company).order_by(
        "-created_at"
    )[:5]

    context = {
        "company": company,
        "items": items,
        "total_products": total_products,
        "total_views": total_views,
        "avg_rating": avg_rating,
        "total_reviews": total_reviews,
        "category_labels": json.dumps(category_labels),
        "category_views": json.dumps(category_views),
        "status_labels": json.dumps(status_labels),
        "status_data": json.dumps(status_data),
        "trending_items": trending_items,
        "suggestions": suggestions,
        "recent_reviews": recent_reviews,
        "recent_comments": recent_comments,
    }
    return render(request, "company/dashboard.html", context)


@login_required
def personal_dashboard(request):
    # Filter items sold by the user (excluding those assigned to a company profile if any,
    # or just all items by this user if you want a unified view)
    items = Item.objects.filter(seller=request.user).order_by("-created_at")

    # Overview Stats
    total_products = items.count()
    total_views = items.aggregate(Sum("views"))["views__sum"] or 0

    # Comments on User's Products
    recent_comments = Comment.objects.filter(item__seller=request.user).order_by(
        "-created_at"
    )[:20]

    # Graph 1: Views per Category
    views_per_category = (
        items.values("category_obj__name")
        .annotate(total_views=Sum("views"))
        .order_by("-total_views")
    )
    cat_labels = [
        x["category_obj__name"] or "Uncategorized" for x in views_per_category
    ]
    cat_data = [x["total_views"] for x in views_per_category]

    # Graph 2: Items Status
    status_counts = items.values("status").annotate(count=Count("id"))
    status_labels = [x["status"].title() for x in status_counts]
    status_data = [x["count"] for x in status_counts]

    # Trending (Top Viewed)
    trending_items = items.order_by("-views")[:5]

    watchlist_count = 0
    if hasattr(request.user, "profile"):
        watchlist_count = request.user.profile.watchlist.count()

    # Dummy data for spending/orders (until Order model is implemented)
    spending_labels = ["Electronics", "Food", "Fashion"]
    spending_data = [0, 0, 0]
    recent_orders = []

    context = {
        "items": items,
        "total_products": total_products,
        "total_views": total_views,
        "cat_labels": json.dumps(cat_labels),
        "cat_data": json.dumps(cat_data),
        "status_labels": json.dumps(status_labels),
        "status_data": json.dumps(status_data),
        "trending_items": trending_items,
        "recent_comments": recent_comments,
        "spending_labels": json.dumps(spending_labels),
        "spending_data": json.dumps(spending_data),
        "recent_orders": recent_orders,
        "watchlist_count": watchlist_count,
    }

    return render(request, "business/personal_dashboard.html", context)


@login_required
def notifications_view(request):
    notifications = request.user.notifications.all()
    return render(
        request, "business/notifications.html", {"notifications": notifications}
    )


@login_required
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(
        Notification, id=notification_id, recipient=request.user
    )
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    return redirect("business:user_notifications")


@login_required
def mark_all_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect("business:user_notifications")


@login_required
def toggle_pin_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.company and item.company.user == request.user:
        item.is_pinned = not item.is_pinned
        item.save()
    return redirect("company:profile", company_id=item.company.id)
