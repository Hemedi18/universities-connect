from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.urls import reverse
from django.core.cache import cache
from django.views.decorators.http import require_POST
import json

from .models import Conversation, ItemDeal, Message
from .forms import MessageForm
from . import deals as deal_svc


def _item_payload(message):
    if not message.item_id:
        return None
    item = message.item
    return {
        "id": item.id,
        "title": item.title,
        "price": f"{item.price:.0f}",
        "url": reverse("customer:item_detail", args=[item.id]),
        "image": item.image.url if item.image else "",
        "status": item.status,
        "stock": item.stock_quantity,
    }


def _active_deals_for_viewer(conversation, viewer):
    qs = list(
        ItemDeal.objects.filter(conversation=conversation)
        .select_related("item")
        .order_by("-updated_at")[:8]
    )
    # Prefer pending, then sold, for header icon
    qs.sort(
        key=lambda d: (
            0 if d.status == ItemDeal.PENDING else 1 if d.status == ItemDeal.SOLD else 2,
            -d.updated_at.timestamp() if d.updated_at else 0,
        )
    )
    return [deal_svc.deal_payload(d, viewer) for d in qs]


@login_required
def inbox(request):
    conversations = Conversation.objects.filter(participants=request.user).order_by(
        "-updated_at"
    )
    chats = []
    seen_users = set()

    for conv in conversations:
        other_user = conv.participants.exclude(id=request.user.id).first()
        if other_user:
            if other_user.id in seen_users:
                continue
            seen_users.add(other_user.id)

            last_message = conv.messages.last()
            unread_count = (
                conv.messages.filter(is_read=False).exclude(sender=request.user).count()
            )
            chats.append(
                {
                    "conversation": conv,
                    "other_user": other_user,
                    "last_message": last_message,
                    "unread_count": unread_count,
                }
            )
    return render(request, "chat/inbox.html", {"chats": chats})


@login_required
def chat_room(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return redirect("chat:inbox")

    unread_messages = conversation.messages.filter(is_read=False).exclude(
        sender=request.user
    )
    unread_messages.update(is_read=True)

    other_user = conversation.participants.exclude(id=request.user.id).first()
    if not other_user:

        class DeletedUser:
            username = "Deleted User"
            first_name = "Deleted User"
            id = None

            def __str__(self):
                return self.username

        other_user = DeletedUser()

    if request.method == "POST":
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            message = form.save(commit=False)
            message.conversation = conversation
            message.sender = request.user
            message.save()
            conversation.save()

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(
                    {
                        "status": "success",
                        "message": {
                            "id": message.id,
                            "content": message.content,
                            "image_url": message.image.url if message.image else None,
                            "timestamp": message.timestamp.strftime("%I:%M %p"),
                            "sender_id": request.user.id,
                            "item": _item_payload(message),
                        },
                    }
                )
            return redirect("chat:chat_room", conversation_id=conversation.id)
    else:
        form = MessageForm()

    deal_list = _active_deals_for_viewer(conversation, request.user)

    # Ensure deals exist for item-linked messages already in the thread
    if other_user and getattr(other_user, "id", None):
        item_ids = (
            conversation.messages.exclude(item_id=None)
            .values_list("item_id", "item__seller_id")
            .distinct()
        )
        for item_id, seller_id in item_ids:
            if not item_id or not seller_id:
                continue
            if request.user.id == seller_id:
                buyer = other_user
                seller = request.user
            elif other_user.id == seller_id:
                buyer = request.user
                seller = other_user
            else:
                continue
            from business.models import Item

            item = Item.objects.filter(pk=item_id).first()
            if item:
                deal_svc.ensure_item_deal(
                    conversation=conversation,
                    item=item,
                    buyer=buyer,
                    seller=seller,
                )
        deal_list = _active_deals_for_viewer(conversation, request.user)

    rating_deal = next((d for d in deal_list if d.get("rating_requested")), None)

    return render(
        request,
        "chat/chat_room.html",
        {
            "conversation": conversation,
            "messages": conversation.messages.select_related("item").all(),
            "form": form,
            "other_user": other_user,
            "deals": deal_list,
            "rating_deal": rating_deal,
        },
    )


@login_required
def start_chat(request, user_id):
    from business.contacts import build_chat_inquiry_text
    from business.models import Item

    target_user = get_object_or_404(User, id=user_id)
    if target_user.id == request.user.id:
        return redirect("chat:inbox")

    conversation = (
        Conversation.objects.filter(participants=request.user)
        .filter(participants=target_user)
        .first()
    )
    if not conversation:
        conversation = Conversation.objects.create()
        conversation.participants.add(request.user, target_user)

    item_id = request.GET.get("item")
    if item_id:
        item = (
            Item.objects.filter(pk=item_id, status="active")
            .select_related("seller")
            .first()
        )
        if item and item.seller_id == target_user.id:
            text = build_chat_inquiry_text(item)
            last = conversation.messages.order_by("-timestamp").first()
            if not last or last.item_id != item.id or last.sender_id != request.user.id:
                msg = Message(
                    conversation=conversation,
                    sender=request.user,
                    content=text,
                    item=item,
                )
                msg.save()
                conversation.save()
            deal_svc.ensure_item_deal(
                conversation=conversation,
                item=item,
                buyer=request.user,
                seller=target_user,
            )

    return redirect("chat:chat_room", conversation_id=conversation.id)


@login_required
def get_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id)
    if request.user not in conversation.participants.all():
        return JsonResponse({"error": "Unauthorized"}, status=403)

    cache.set(f"user_online_{request.user.id}", True, 10)

    last_id = request.GET.get("last_id") or request.GET.get("after")
    messages = conversation.messages.select_related("item").all()

    if last_id:
        messages = messages.filter(id__gt=last_id)

    unread = messages.exclude(sender=request.user).filter(is_read=False)
    unread.update(is_read=True)

    other_user = conversation.participants.exclude(id=request.user.id).first()
    other_online = cache.get(f"user_online_{other_user.id}") if other_user else False

    data = []
    for msg in messages:
        status = "sent"
        if msg.is_read:
            status = "read"
        elif other_online:
            status = "delivered"

        data.append(
            {
                "id": msg.id,
                "sender_id": msg.sender_id,
                "content": msg.content,
                "image_url": msg.image.url if msg.image else None,
                "timestamp": msg.timestamp.strftime("%I:%M %p"),
                "is_sent": msg.sender_id == request.user.id,
                "status": status,
                "item": _item_payload(msg),
            }
        )

    status_updates = []
    recent_sent = conversation.messages.filter(sender=request.user).order_by("-id")[:30]
    for msg in recent_sent:
        s = "sent"
        if msg.is_read:
            s = "read"
        elif other_online:
            s = "delivered"
        status_updates.append({"id": msg.id, "status": s})

    partner_info = {}
    if other_user:
        partner_info["name"] = other_user.username
        partner_info["is_online"] = other_online
        try:
            if hasattr(other_user, "profile") and other_user.profile.image:
                partner_info["avatar"] = other_user.profile.image.url
        except Exception:
            pass

    deals = _active_deals_for_viewer(conversation, request.user)
    rating_deal = next((d for d in deals if d.get("rating_requested")), None)

    return JsonResponse(
        {
            "messages": data,
            "statuses": status_updates,
            "partner": partner_info,
            "deals": deals,
            "rating_deal": rating_deal,
        }
    )


@login_required
@require_POST
def deal_mark_sold(request, deal_id):
    deal = get_object_or_404(
        ItemDeal.objects.select_related("item", "buyer", "seller"), pk=deal_id
    )
    if request.user.id != deal.seller_id:
        return JsonResponse({"error": "Seller only"}, status=403)
    try:
        body = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        body = {}
    qty = body.get("quantity") or request.POST.get("quantity") or 1
    try:
        deal = deal_svc.mark_deal_sold(deal, qty)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"ok": True, "deal": deal_svc.deal_payload(deal, request.user)})


@login_required
@require_POST
def deal_mark_not_sold(request, deal_id):
    deal = get_object_or_404(ItemDeal, pk=deal_id)
    if request.user.id != deal.seller_id:
        return JsonResponse({"error": "Seller only"}, status=403)
    deal = deal_svc.mark_deal_not_sold(deal)
    return JsonResponse({"ok": True, "deal": deal_svc.deal_payload(deal, request.user)})


@login_required
@require_POST
def deal_update_stock(request, deal_id):
    deal = get_object_or_404(ItemDeal.objects.select_related("item"), pk=deal_id)
    if request.user.id != deal.seller_id:
        return JsonResponse({"error": "Seller only"}, status=403)
    try:
        body = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        body = {}
    stock = body.get("stock_quantity")
    if stock is None:
        stock = request.POST.get("stock_quantity")
    try:
        item = deal_svc.update_item_stock_after_sale(deal, stock)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    deal.refresh_from_db()
    payload = deal_svc.deal_payload(deal, request.user)
    payload["stock_quantity"] = item.stock_quantity
    return JsonResponse({"ok": True, "deal": payload})


@login_required
@require_POST
def deal_submit_rating(request, deal_id):
    deal = get_object_or_404(
        ItemDeal.objects.select_related("item", "buyer", "seller"), pk=deal_id
    )
    try:
        body = json.loads(request.body.decode() or "{}")
    except json.JSONDecodeError:
        body = {}
    rating = body.get("rating") or request.POST.get("rating")
    comment = body.get("comment") or request.POST.get("comment") or ""
    try:
        deal_svc.submit_deal_rating(deal, request.user, rating, comment)
    except (PermissionError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    deal.refresh_from_db()
    return JsonResponse({"ok": True, "deal": deal_svc.deal_payload(deal, request.user)})


@login_required
def update_typing_status(request, conversation_id):
    if request.method == "POST":
        key = f"typing_conversation_{conversation_id}_user_{request.user.id}"
        cache.set(key, True, 3)
        return JsonResponse({"status": "success"})
    return JsonResponse({"status": "error"}, status=400)


@login_required
def check_typing_status(request, conversation_id):
    other_user_id = request.GET.get("other_user_id")

    if other_user_id:
        key = f"typing_conversation_{conversation_id}_user_{other_user_id}"
        is_typing = cache.get(key)
        return JsonResponse({"is_typing": bool(is_typing)})

    return JsonResponse({"is_typing": False})


def get_total_unread(request):
    if not request.user.is_authenticated:
        return JsonResponse({"count": 0})
    count = (
        Message.objects.filter(
            conversation__participants=request.user, is_read=False
        )
        .exclude(sender=request.user)
        .count()
    )
    return JsonResponse({"count": count})
