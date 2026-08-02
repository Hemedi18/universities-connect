from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from django.urls import reverse

from business.models import Item, Notification

from .models import DealRating, ItemDeal


def ensure_item_deal(*, conversation, item, buyer, seller) -> ItemDeal:
    deal, _ = ItemDeal.objects.get_or_create(
        conversation=conversation,
        item=item,
        buyer=buyer,
        defaults={"seller": seller, "status": ItemDeal.PENDING},
    )
    return deal


def deal_payload(deal: ItemDeal, viewer) -> dict:
    has_rating = hasattr(deal, "rating") and deal.rating is not None
    try:
        has_rating = DealRating.objects.filter(deal=deal).exists()
    except Exception:
        has_rating = False

    is_seller = viewer.id == deal.seller_id
    is_buyer = viewer.id == deal.buyer_id
    return {
        "id": deal.id,
        "item_id": deal.item_id,
        "item_title": deal.item.title if deal.item_id else "",
        "status": deal.status,
        "quantity": deal.quantity,
        "stock_quantity": deal.item.stock_quantity if deal.item_id else 0,
        "is_seller": is_seller,
        "is_buyer": is_buyer,
        "rating_requested": bool(deal.rating_requested and is_buyer and not has_rating),
        "has_rating": has_rating,
        "can_manage_stock": is_seller and deal.status == ItemDeal.SOLD,
        "max_qty": max(1, deal.item.stock_quantity) if deal.item_id else 1,
    }


@transaction.atomic
def mark_deal_sold(deal: ItemDeal, quantity: int) -> ItemDeal:
    if deal.status == ItemDeal.SOLD:
        return deal

    item = Item.objects.select_for_update().get(pk=deal.item_id)
    qty = max(1, int(quantity or 1))
    if qty > item.stock_quantity:
        qty = item.stock_quantity
    if qty < 1:
        raise ValueError("Hakuna stock ya kutosha.")

    new_stock = item.stock_quantity - qty
    updates = {
        "stock_quantity": new_stock,
        "buyer_id": deal.buyer_id,
    }
    if new_stock <= 0:
        updates["status"] = "sold"
    Item.objects.filter(pk=item.pk).update(**updates)

    deal.status = ItemDeal.SOLD
    deal.quantity = qty
    deal.rating_requested = True
    deal.closed_at = timezone.now()
    deal.save(
        update_fields=[
            "status",
            "quantity",
            "rating_requested",
            "closed_at",
            "updated_at",
        ]
    )

    Notification.objects.create(
        recipient=deal.buyer,
        message=f"Muuzaji amethibitisha umenunua: {item.title}. Tafadhali toa rating.",
        link=reverse("chat:chat_room", args=[deal.conversation_id]),
    )
    return deal


@transaction.atomic
def mark_deal_not_sold(deal: ItemDeal) -> ItemDeal:
    deal.status = ItemDeal.NOT_SOLD
    deal.rating_requested = False
    deal.closed_at = timezone.now()
    deal.save(
        update_fields=["status", "rating_requested", "closed_at", "updated_at"]
    )
    return deal


@transaction.atomic
def update_item_stock_after_sale(deal: ItemDeal, new_stock: int) -> Item:
    if deal.status != ItemDeal.SOLD:
        raise ValueError("Badilisha stock baada ya kuweka sold.")
    item = Item.objects.select_for_update().get(pk=deal.item_id)
    stock = max(0, int(new_stock))
    status = "active" if stock > 0 else "sold"
    Item.objects.filter(pk=item.pk).update(stock_quantity=stock, status=status)
    item.refresh_from_db()
    return item


@transaction.atomic
def submit_deal_rating(deal: ItemDeal, buyer, rating: int, comment: str = "") -> DealRating:
    if deal.buyer_id != buyer.id:
        raise PermissionError("Ni mnunuzi pekee anayeweza kutoa rating.")
    if deal.status != ItemDeal.SOLD:
        raise ValueError("Rating inapatikana baada ya sold.")
    if DealRating.objects.filter(deal=deal).exists():
        raise ValueError("Umeshatoa rating tayari.")

    stars = max(1, min(5, int(rating)))
    obj = DealRating.objects.create(
        deal=deal,
        item_id=deal.item_id,
        buyer=buyer,
        seller_id=deal.seller_id,
        rating=stars,
        comment=(comment or "").strip()[:2000],
    )
    deal.rating_requested = False
    deal.save(update_fields=["rating_requested", "updated_at"])

    # Mirror into company review when listing belongs to a company
    item = deal.item
    if item and item.company_id:
        from company.models import Review

        Review.objects.create(
            company_id=item.company_id,
            user=buyer,
            rating=stars,
            comment=obj.comment or f"Rated {stars}/5 via chat sale",
        )

    Notification.objects.create(
        recipient=deal.seller,
        message=f"{buyer.username} amekupa rating {stars}★ kwa {item.title}",
        link=reverse("customer:item_detail", args=[item.id]) if item else "",
    )
    return obj
