from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Count, Avg
from django.views.decorators.http import require_POST
from .forms import ItemForm, MAX_ITEM_MEDIA, save_item_media_files, validate_uploaded_media
from .models import Item, ItemMedia, Category, Notification, Comment, SellerMeetupLocation
from .analytics import get_user_analytics, get_user_storage_breakdown
from django.http import JsonResponse
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


def save_item_media_urls(item, urls, start_order=0):
    """Download and create ItemMedia rows from external image or video URLs."""
    import os
    import urllib.request
    from urllib.parse import urlparse
    from django.core.files.base import ContentFile
    from .forms import resize_uploaded_image

    added = 0
    order = start_order
    headers = {"User-Agent": "Mozilla/5.0 (compatible; U-ConnectBot/1.0; +https://uconnect.edusphere.co.tz)"}

    for url in urls:
        url = (url or "").strip()
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            continue
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                content_type = (resp.headers.get_content_type() or "").lower()
                content = resp.read(25 * 1024 * 1024 + 10)
                if len(content) > 25 * 1024 * 1024:
                    continue

                parsed = urlparse(url)
                ext = os.path.splitext(parsed.path)[1].lower()
                if not ext:
                    if "video" in content_type:
                        ext = ".mp4"
                    elif "png" in content_type:
                        ext = ".png"
                    elif "webp" in content_type:
                        ext = ".webp"
                    else:
                        ext = ".jpg"

                filename = f"url_media_{item.id}_{order}{ext}"
                cfile = ContentFile(content, name=filename)

                if "video" in content_type or ext in (".mp4", ".webm", ".mov", ".m4v"):
                    mtype = ItemMedia.MEDIA_VIDEO
                else:
                    mtype = ItemMedia.MEDIA_IMAGE
                    try:
                        resize_uploaded_image(cfile)
                    except Exception:
                        pass

                ItemMedia.objects.create(
                    item=item,
                    file=cfile,
                    media_type=mtype,
                    sort_order=order,
                )
                order += 1
                added += 1
        except Exception:
            continue

    if added:
        item.sync_legacy_media_fields()
    return added


def _process_item_media(request, item, *, require_image=False):
    """Handle remove_media_ids + media_files uploads + media_urls. Returns error message or None."""
    remove_ids = request.POST.getlist("remove_media_ids")
    if remove_ids:
        ItemMedia.objects.filter(item=item, id__in=remove_ids).delete()
        # Re-sequence
        for i, media in enumerate(item.media.order_by("sort_order", "id")):
            if media.sort_order != i:
                media.sort_order = i
                media.save(update_fields=["sort_order"])

    uploads = request.FILES.getlist("media_files")
    media_urls = [u.strip() for u in request.POST.getlist("media_urls") if u.strip()]
    existing = item.media.count()
    if existing + len(uploads) + len(media_urls) > MAX_ITEM_MEDIA:
        return f"Maximum {MAX_ITEM_MEDIA} photos/videos per item."

    try:
        for uploaded in uploads:
            validate_uploaded_media(uploaded)
        if uploads:
            save_item_media_files(item, uploads, start_order=existing)
            existing = item.media.count()

        if media_urls:
            save_item_media_urls(item, media_urls, start_order=existing)

        if not uploads and not media_urls:
            item.sync_legacy_media_fields()
    except ValidationError as exc:
        return "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc)

    has_image = item.media.filter(media_type=ItemMedia.MEDIA_IMAGE).exists() or bool(
        item.image
    )
    if require_image and not has_image:
        return "Weka angalau picha 1 ya bidhaa (Add at least one product photo)."
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

    email = (request.user.email or "").strip()

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

    saved_locations = list(
        SellerMeetupLocation.objects.filter(user=request.user).order_by("-is_default", "-created_at")
    )
    default_loc = next((loc for loc in saved_locations if loc.is_default), None)
    saved_locations_data = [
        {
            "id": loc.id,
            "general_location": loc.general_location,
            "specific_location": loc.specific_location,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "is_default": loc.is_default,
        }
        for loc in saved_locations
    ]

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

            # Handle remembering location or setting default
            remember = form.cleaned_data.get("remember_location")
            set_default = form.cleaned_data.get("set_as_default_location")
            gen_loc = (item.general_location or "").strip()
            spec_loc = (item.specific_location or "").strip()

            if (remember or set_default) and (gen_loc or spec_loc):
                if set_default:
                    SellerMeetupLocation.objects.filter(user=request.user).update(is_default=False)
                loc, created = SellerMeetupLocation.objects.get_or_create(
                    user=request.user,
                    general_location=gen_loc,
                    specific_location=spec_loc,
                    defaults={
                        "latitude": item.location_latitude,
                        "longitude": item.location_longitude,
                        "is_default": bool(set_default),
                    },
                )
                if not created:
                    if item.location_latitude is not None:
                        loc.latitude = item.location_latitude
                    if item.location_longitude is not None:
                        loc.longitude = item.location_longitude
                    if set_default:
                        loc.is_default = True
                    loc.save()

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
        # Pre-fill registered phone, email, and default location by default for seller convenience
        initial_data = {
            "contact_phone": phone,
            "contact_email": email,
            "contact_method": "phone",
        }
        if default_loc:
            initial_data.update({
                "general_location": default_loc.general_location,
                "specific_location": default_loc.specific_location,
                "location_latitude": default_loc.latitude,
                "location_longitude": default_loc.longitude,
                "remember_location": True,
                "set_as_default_location": True,
            })
        form = ItemForm(
            category=category,
            initial=initial_data,
        )
    return render(
        request,
        "business/post_item.html",
        {
            "form": form,
            "category": category,
            "existing_media": [],
            "max_media": MAX_ITEM_MEDIA,
            "registered_phone": phone,
            "registered_email": email,
            "saved_locations": saved_locations,
            "saved_locations_json": json.dumps(saved_locations_data),
            "default_location": default_loc,
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

    saved_locations = list(
        SellerMeetupLocation.objects.filter(user=request.user).order_by("-is_default", "-created_at")
    )
    default_loc = next((loc for loc in saved_locations if loc.is_default), None)
    saved_locations_data = [
        {
            "id": loc.id,
            "general_location": loc.general_location,
            "specific_location": loc.specific_location,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "is_default": loc.is_default,
        }
        for loc in saved_locations
    ]

    if request.method == "POST":
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()

            remember = form.cleaned_data.get("remember_location")
            set_default = form.cleaned_data.get("set_as_default_location")
            gen_loc = (item.general_location or "").strip()
            spec_loc = (item.specific_location or "").strip()

            if (remember or set_default) and (gen_loc or spec_loc):
                if set_default:
                    SellerMeetupLocation.objects.filter(user=request.user).update(is_default=False)
                loc, created = SellerMeetupLocation.objects.get_or_create(
                    user=request.user,
                    general_location=gen_loc,
                    specific_location=spec_loc,
                    defaults={
                        "latitude": item.location_latitude,
                        "longitude": item.location_longitude,
                        "is_default": bool(set_default),
                    },
                )
                if not created:
                    if item.location_latitude is not None:
                        loc.latitude = item.location_latitude
                    if item.location_longitude is not None:
                        loc.longitude = item.location_longitude
                    if set_default:
                        loc.is_default = True
                    loc.save()

            err = _process_item_media(request, item, require_image=True)
            if err:
                messages.error(request, err)
            else:
                messages.success(request, "Item updated.")
                return redirect("business:manage_items")
    else:
        form = ItemForm(instance=item)
    profile = getattr(request.user, "profile", None)
    phone = (getattr(profile, "phone_number", None) or "").strip()
    email = (request.user.email or "").strip()
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
            "registered_phone": phone,
            "registered_email": email,
            "saved_locations": saved_locations,
            "saved_locations_json": json.dumps(saved_locations_data),
            "default_location": default_loc,
        },
    )


@login_required
@require_POST
def set_default_location(request, location_id):
    loc = get_object_or_404(SellerMeetupLocation, id=location_id, user=request.user)
    SellerMeetupLocation.objects.filter(user=request.user).exclude(id=loc.id).update(is_default=False)
    loc.is_default = True
    loc.save(update_fields=["is_default"])
    return JsonResponse({
        "success": True,
        "message": "Location set as default.",
        "location": {
            "id": loc.id,
            "general_location": loc.general_location,
            "specific_location": loc.specific_location,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "is_default": True,
        },
    })


@login_required
@require_POST
def delete_saved_location(request, location_id):
    loc = get_object_or_404(SellerMeetupLocation, id=location_id, user=request.user)
    loc.delete()
    return JsonResponse({"success": True, "message": "Saved location removed."})


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
    analytics = get_user_analytics(request.user)
    items = Item.objects.filter(seller=request.user).order_by("-created_at")

    total_products = analytics.get("total_listings", items.count())
    total_views = analytics.get("total_views", 0)
    total_clicks = analytics.get("total_clicks", 0)
    click_through_rate = analytics.get("click_through_rate", 0.0)
    total_read_chats = analytics.get("total_read_chats", 0)
    total_buyers = analytics.get("total_buyers", 0)
    storage = analytics.get("storage", {})
    categories_data = analytics.get("categories", [])

    # Comments on User's Products
    recent_comments = Comment.objects.filter(item__seller=request.user).order_by(
        "-created_at"
    )[:20]

    # Product status counts
    status_counts = items.values("status").annotate(count=Count("id"))
    status_labels = [x["status"].title() for x in status_counts]
    status_data = [x["count"] for x in status_counts]

    # Trending (Top Viewed)
    trending_items = items.order_by("-views")[:6]

    watchlist_count = 0
    if hasattr(request.user, "profile"):
        watchlist_count = request.user.profile.watchlist.count()

    context = {
        "items": items,
        "total_products": total_products,
        "active_listings": analytics.get("active_listings", 0),
        "sold_listings": analytics.get("sold_listings", 0),
        "total_views": total_views,
        "total_clicks": total_clicks,
        "click_through_rate": click_through_rate,
        "total_read_chats": total_read_chats,
        "total_buyers": total_buyers,
        "storage": storage,
        "categories_data": categories_data,
        "trending_items": trending_items,
        "recent_comments": recent_comments,
        "watchlist_count": watchlist_count,
        "status_labels": json.dumps(status_labels),
        "status_data": json.dumps(status_data),
        # Chart.js JSON datasets
        "chart_categories_json": analytics.get("chart_categories_json", "[]"),
        "chart_views_json": analytics.get("chart_views_json", "[]"),
        "chart_clicks_json": analytics.get("chart_clicks_json", "[]"),
        "chart_chats_json": analytics.get("chart_chats_json", "[]"),
        "chart_buyers_json": analytics.get("chart_buyers_json", "[]"),
        "chart_storage_mb_json": analytics.get("chart_storage_mb_json", "[]"),
        # Legacy compatibility
        "cat_labels": analytics.get("chart_categories_json", "[]"),
        "cat_data": analytics.get("chart_views_json", "[]"),
    }

    return render(request, "business/personal_dashboard.html", context)


@login_required
@require_POST
def upgrade_storage_plan(request):
    """
    Handle upgrade storage tier request.
    Prepared cleanly for billing/payment gateway integration (M-Pesa, Tigo Pesa, TanCoin).
    """
    plan = request.POST.get("plan_code") or request.POST.get("plan") or "pro"
    PLAN_QUOTAS = {
        "free": 100,
        "pro": 1000,
        "business": 5000,
    }
    if plan not in PLAN_QUOTAS:
        messages.error(request, "Invalid storage plan selected.")
        return redirect("business:personal_dashboard")

    profile = getattr(request.user, "profile", None)
    if profile:
        profile.storage_plan = plan
        profile.storage_quota_mb = PLAN_QUOTAS[plan]
        profile.save(update_fields=["storage_plan", "storage_quota_mb"])
        messages.success(
            request,
            f"Storage plan updated to {profile.get_storage_plan_display()} ({profile.storage_quota_mb} MB)!",
        )
    else:
        messages.error(request, "User profile not found.")
    return redirect("business:personal_dashboard")


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
