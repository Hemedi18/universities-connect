from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import F
from django.utils import timezone

from .models import InteractionEvent, ItemFeature, UserFeature


EVENT_WEIGHTS = {
    InteractionEvent.VIEW: 1,
    InteractionEvent.CLICK: 2,
    InteractionEvent.ADD_TO_CART: 4,
    InteractionEvent.PURCHASE: 8,
    InteractionEvent.SEARCH: 1,
    InteractionEvent.WATCHLIST: 3,
}


def ensure_session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ""


def log_event(
    *,
    event_type: str,
    item_id: int | None = None,
    user: AbstractBaseUser | None = None,
    session_key: str = "",
    metadata: dict | None = None,
    bump_features: bool = True,
) -> InteractionEvent:
    event = InteractionEvent.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        session_key=session_key or "",
        item_id=item_id,
        event_type=event_type,
        metadata=metadata or {},
    )
    if bump_features:
        _bump_short_term_features(event)
    return event


def log_event_from_request(
    request,
    event_type: str,
    item_id: int | None = None,
    metadata: dict | None = None,
) -> InteractionEvent:
    session_key = ensure_session_key(request)
    user = request.user if getattr(request.user, "is_authenticated", False) else None
    return log_event(
        event_type=event_type,
        item_id=item_id,
        user=user,
        session_key=session_key,
        metadata=metadata,
    )


def _get_or_create_user_feature(user=None, session_key: str = "") -> UserFeature | None:
    if user and getattr(user, "is_authenticated", False):
        feat, _ = UserFeature.objects.get_or_create(user=user)
        return feat
    if session_key:
        feat, _ = UserFeature.objects.get_or_create(
            session_key=session_key,
            defaults={"user": None},
        )
        return feat
    return None


def _bump_short_term_features(event: InteractionEvent) -> None:
    now = timezone.now()
    uf = _get_or_create_user_feature(event.user, event.session_key)
    if uf:
        updates: dict[str, Any] = {"last_active": now}
        if event.event_type == InteractionEvent.VIEW:
            UserFeature.objects.filter(pk=uf.pk).update(
                view_count=F("view_count") + 1, last_active=now
            )
        elif event.event_type == InteractionEvent.CLICK:
            UserFeature.objects.filter(pk=uf.pk).update(
                click_count=F("click_count") + 1, last_active=now
            )
        elif event.event_type == InteractionEvent.ADD_TO_CART:
            UserFeature.objects.filter(pk=uf.pk).update(
                cart_count=F("cart_count") + 1, last_active=now
            )
        elif event.event_type == InteractionEvent.PURCHASE:
            UserFeature.objects.filter(pk=uf.pk).update(
                purchase_count=F("purchase_count") + 1, last_active=now
            )
        else:
            UserFeature.objects.filter(pk=uf.pk).update(**updates)

        if event.item_id:
            uf.refresh_from_db()
            recent = list(uf.recent_item_ids or [])
            if event.item_id in recent:
                recent.remove(event.item_id)
            recent.insert(0, event.item_id)
            uf.recent_item_ids = recent[:30]
            cat_id = getattr(event.item, "category_obj_id", None)
            if cat_id is None and event.item_id:
                from business.models import Item

                cat_id = (
                    Item.objects.filter(pk=event.item_id)
                    .values_list("category_obj_id", flat=True)
                    .first()
                )
            if cat_id:
                affinity = dict(uf.category_affinity or {})
                key = str(cat_id)
                weight = EVENT_WEIGHTS.get(event.event_type, 1)
                affinity[key] = float(affinity.get(key, 0)) + weight
                uf.category_affinity = affinity
            uf.save(update_fields=["recent_item_ids", "category_affinity", "updated_at"])

    if event.item_id:
        ife, _ = ItemFeature.objects.get_or_create(
            item_id=event.item_id,
            defaults={"category_id": getattr(event.item, "category_obj_id", None)},
        )
        field_map = {
            InteractionEvent.VIEW: "view_count",
            InteractionEvent.CLICK: "click_count",
            InteractionEvent.ADD_TO_CART: "cart_count",
            InteractionEvent.PURCHASE: "purchase_count",
        }
        field = field_map.get(event.event_type)
        if field:
            ItemFeature.objects.filter(pk=ife.pk).update(**{field: F(field) + 1})
            ItemFeature.objects.filter(pk=ife.pk).update(
                popularity_score=(
                    F("view_count") * 1.0
                    + F("click_count") * 2.0
                    + F("cart_count") * 4.0
                    + F("purchase_count") * 8.0
                )
            )
