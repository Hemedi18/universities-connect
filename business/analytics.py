import json
from decimal import Decimal
from django.conf import settings
from django.db.models import Sum, Count, Q
from django.contrib.auth.models import User
from business.models import Item, ItemMedia, Category
from recommend.models import InteractionEvent
from chat.models import Message, ItemDeal
from customer.models import OrderItem


def format_bytes(num_bytes: int) -> str:
    """Format bytes into human-readable string (B, KB, MB, GB)."""
    if not num_bytes or num_bytes <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}" if unit in ["MB", "GB"] else f"{num_bytes:.0f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def get_user_storage_breakdown(user: User, quota_mb: int = None, plan_name: str = None) -> dict:
    """
    Calculate the exact disk space used by a user across:
    - Product images and videos (ItemMedia)
    - Legacy product files (Item image/video fields)
    - Profile avatar
    - Chat attachment images sent by the user
    """
    if not user or not user.is_authenticated:
        return {
            "total_bytes": 0,
            "total_mb": 0.0,
            "quota_mb": 100,
            "quota_bytes": 100 * 1024 * 1024,
            "used_percentage": 0.0,
            "free_bytes": 100 * 1024 * 1024,
            "free_formatted": "100 MB",
            "total_formatted": "0 B",
            "quota_formatted": "100 MB",
            "plan_name": "Free Tier",
            "status": "healthy",
            "images_bytes": 0,
            "images_count": 0,
            "images_formatted": "0 B",
            "videos_bytes": 0,
            "videos_count": 0,
            "videos_formatted": "0 B",
            "chat_bytes": 0,
            "chat_count": 0,
            "chat_formatted": "0 B",
            "profile_bytes": 0,
            "profile_count": 0,
            "profile_formatted": "0 B",
            "category_storage": {},
        }

    profile = getattr(user, "profile", None)
    if quota_mb is None:
        quota_mb = getattr(profile, "storage_quota_mb", 100) or 100
    if plan_name is None:
        plan_name = profile.get_storage_plan_display() if profile and hasattr(profile, "get_storage_plan_display") else "Free Tier (100 MB)"

    quota_bytes = quota_mb * 1024 * 1024

    images_bytes = 0
    images_count = 0
    videos_bytes = 0
    videos_count = 0
    category_storage_map = {}  # category_id -> int bytes

    # 1. Product Media (ItemMedia)
    user_media = ItemMedia.objects.filter(item__seller=user).select_related("item", "item__category_obj")
    seen_file_names = set()

    for m in user_media:
        if not m.file:
            continue
        try:
            sz = m.file.size
        except Exception:
            sz = 0
        if sz <= 0:
            continue

        seen_file_names.add(m.file.name)
        cat_id = m.item.category_obj_id or 0
        category_storage_map[cat_id] = category_storage_map.get(cat_id, 0) + sz

        if m.media_type == ItemMedia.MEDIA_VIDEO:
            videos_bytes += sz
            videos_count += 1
        else:
            images_bytes += sz
            images_count += 1

    # 2. Legacy Product fields (if not already counted in ItemMedia)
    legacy_items = Item.objects.filter(seller=user).select_related("category_obj")
    for item in legacy_items:
        cat_id = item.category_obj_id or 0
        for field_name in ["image", "image2", "image3", "video"]:
            f = getattr(item, field_name, None)
            if f and f.name and f.name not in seen_file_names:
                try:
                    sz = f.size
                except Exception:
                    sz = 0
                if sz > 0:
                    seen_file_names.add(f.name)
                    category_storage_map[cat_id] = category_storage_map.get(cat_id, 0) + sz
                    if field_name == "video":
                        videos_bytes += sz
                        videos_count += 1
                    else:
                        images_bytes += sz
                        images_count += 1

    # 3. Chat Media sent by this user
    chat_bytes = 0
    chat_count = 0
    for msg in Message.objects.filter(sender=user).exclude(image=""):
        if msg.image:
            try:
                sz = msg.image.size
            except Exception:
                sz = 0
            if sz > 0:
                chat_bytes += sz
                chat_count += 1

    # 4. Profile Picture
    profile_bytes = 0
    profile_count = 0
    if profile and profile.profile_picture:
        pname = profile.profile_picture.name or ""
        if "default_profile" not in pname:
            try:
                profile_bytes = profile.profile_picture.size
                profile_count = 1
            except Exception:
                profile_bytes = 0

    total_bytes = images_bytes + videos_bytes + chat_bytes + profile_bytes
    total_mb = round(total_bytes / (1024 * 1024), 2)
    used_percentage = min(100.0, round((total_bytes / quota_bytes) * 100, 1)) if quota_bytes > 0 else 100.0

    if used_percentage >= 100:
        status = "exceeded"
    elif used_percentage >= 90:
        status = "critical"
    elif used_percentage >= 75:
        status = "warning"
    else:
        status = "healthy"

    free_bytes = max(0, quota_bytes - total_bytes)

    return {
        "total_bytes": total_bytes,
        "total_mb": total_mb,
        "quota_mb": quota_mb,
        "quota_bytes": quota_bytes,
        "free_bytes": free_bytes,
        "free_formatted": format_bytes(free_bytes),
        "total_formatted": format_bytes(total_bytes),
        "quota_formatted": f"{quota_mb} MB" if quota_mb < 1000 else f"{quota_mb/1000:.1f} GB",
        "used_percentage": used_percentage,
        "status": status,
        "plan_name": plan_name,
        "images_bytes": images_bytes,
        "images_count": images_count,
        "images_formatted": format_bytes(images_bytes),
        "videos_bytes": videos_bytes,
        "videos_count": videos_count,
        "videos_formatted": format_bytes(videos_bytes),
        "chat_bytes": chat_bytes,
        "chat_count": chat_count,
        "chat_formatted": format_bytes(chat_bytes),
        "profile_bytes": profile_bytes,
        "profile_count": profile_count,
        "profile_formatted": format_bytes(profile_bytes),
        "category_storage": category_storage_map,
    }


def get_user_analytics(user: User) -> dict:
    """
    Compute comprehensive seller analytics for a user:
    - Views (total + per category)
    - Clicks (total + per category)
    - Read chats / inquiries (total + per category)
    - Buyers (unique buyers who purchased items from this seller + per category)
    - Storage breakdown (total + per category)
    """
    if not user or not user.is_authenticated:
        return {}

    items = Item.objects.filter(seller=user).select_related("category_obj")
    total_listings = items.count()
    active_listings = items.filter(status="active").count()
    sold_listings = items.filter(status="sold").count()

    # 1. Total Views
    sum_views = items.aggregate(Sum("views"))["views__sum"] or 0
    event_views = InteractionEvent.objects.filter(item__seller=user, event_type=InteractionEvent.VIEW).count()
    total_views = max(sum_views, event_views)

    # 2. Total Clicks
    total_clicks = InteractionEvent.objects.filter(
        item__seller=user, event_type=InteractionEvent.CLICK
    ).count()

    # 3. Read Chats / Inquiries
    # Direct messages on seller's items that have been read by seller or replied to
    item_read_chats = Message.objects.filter(
        item__seller=user, is_read=True
    ).exclude(sender=user).count()
    # Conversations with deals on seller's items
    deal_read_chats = Message.objects.filter(
        conversation__deals__item__seller=user, is_read=True
    ).exclude(sender=user).distinct().count()
    total_read_chats = max(item_read_chats, deal_read_chats)

    # 4. Total Buyers (Unique users who placed completed/confirmed orders or bought deals)
    order_buyer_ids = set(
        OrderItem.objects.filter(seller=user)
        .values_list("order__buyer_id", flat=True)
        .distinct()
    )
    deal_buyer_ids = set(
        ItemDeal.objects.filter(item__seller=user, status=ItemDeal.SOLD)
        .values_list("buyer_id", flat=True)
        .distinct()
    )
    item_buyer_ids = set(
        Item.objects.filter(seller=user, buyer__isnull=False)
        .values_list("buyer_id", flat=True)
        .distinct()
    )
    all_buyer_ids = (order_buyer_ids | deal_buyer_ids | item_buyer_ids) - {None, user.id}
    total_buyers = len(all_buyer_ids)

    # 5. Disk Storage
    storage_data = get_user_storage_breakdown(user)
    cat_storage_map = storage_data["category_storage"]

    # 6. Category Breakdown
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

    # Group items by category_obj
    categories_dict = {}
    for item in items:
        cat = item.category_obj
        cat_id = cat.id if cat else 0
        cat_name = cat.name if cat else (item.category.title() if item.category else "Uncategorized")
        cat_icon = icon_mapping.get(cat_name, "bi-tag-fill")
        cat_slug = cat.slug if cat else "other"

        if cat_id not in categories_dict:
            categories_dict[cat_id] = {
                "id": cat_id,
                "name": cat_name,
                "icon": cat_icon,
                "slug": cat_slug,
                "items_count": 0,
                "items_ids": [],
                "views": 0,
                "clicks": 0,
                "read_chats": 0,
                "buyer_ids": set(),
                "buyers": 0,
                "disk_bytes": cat_storage_map.get(cat_id, 0),
                "disk_formatted": format_bytes(cat_storage_map.get(cat_id, 0)),
            }

        categories_dict[cat_id]["items_count"] += 1
        categories_dict[cat_id]["items_ids"].append(item.id)
        categories_dict[cat_id]["views"] += (item.views or 0)

    # Enrich categories with clicks, read chats, and buyers
    category_list = list(categories_dict.values())
    for cdata in category_list:
        iids = cdata["items_ids"]
        if iids:
            # Clicks
            cdata["clicks"] = InteractionEvent.objects.filter(
                item_id__in=iids, event_type=InteractionEvent.CLICK
            ).count()

            # Read Chats
            cdata["read_chats"] = Message.objects.filter(
                item_id__in=iids, is_read=True
            ).exclude(sender=user).count()

            # Buyers for this category
            cat_order_buyers = set(
                OrderItem.objects.filter(seller=user, item_id__in=iids)
                .values_list("order__buyer_id", flat=True)
            )
            cat_deal_buyers = set(
                ItemDeal.objects.filter(item_id__in=iids, status=ItemDeal.SOLD)
                .values_list("buyer_id", flat=True)
            )
            cat_item_buyers = set(
                Item.objects.filter(id__in=iids, buyer__isnull=False)
                .values_list("buyer_id", flat=True)
            )
            cdata["buyer_ids"] = (cat_order_buyers | cat_deal_buyers | cat_item_buyers) - {None, user.id}
            cdata["buyers"] = len(cdata["buyer_ids"])

        # Conversion / Engagement rate (clicks + buyers per view)
        if cdata["views"] > 0:
            cdata["conversion_rate"] = round((cdata["clicks"] / cdata["views"]) * 100, 1)
        else:
            cdata["conversion_rate"] = 0.0

    # Sort categories by views descending
    category_list.sort(key=lambda x: (x["views"], x["clicks"], x["items_count"]), reverse=True)

    # Prepare Chart Data Lists
    cat_names = [c["name"] for c in category_list]
    cat_views = [c["views"] for c in category_list]
    cat_clicks = [c["clicks"] for c in category_list]
    cat_chats = [c["read_chats"] for c in category_list]
    cat_buyers = [c["buyers"] for c in category_list]
    cat_storage_mb = [round(c["disk_bytes"] / (1024 * 1024), 2) for c in category_list]

    ctr = round((total_clicks / total_views) * 100, 1) if total_views > 0 else 0.0

    return {
        "total_listings": total_listings,
        "active_listings": active_listings,
        "sold_listings": sold_listings,
        "total_views": total_views,
        "total_clicks": total_clicks,
        "click_through_rate": ctr,
        "total_read_chats": total_read_chats,
        "total_buyers": total_buyers,
        "storage": storage_data,
        "categories": category_list,
        # JSON serialized for Chart.js
        "chart_categories_json": json.dumps(cat_names),
        "chart_views_json": json.dumps(cat_views),
        "chart_clicks_json": json.dumps(cat_clicks),
        "chart_chats_json": json.dumps(cat_chats),
        "chart_buyers_json": json.dumps(cat_buyers),
        "chart_storage_mb_json": json.dumps(cat_storage_mb),
    }
