from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from itertools import combinations

from django.db import transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from business.models import Item
from customer.models import OrderItem

from .models import InteractionEvent, ItemFeature, ItemSimilarity, UserFeature


def _price_band(price) -> int:
    try:
        p = float(price or 0)
    except (TypeError, ValueError):
        return 0
    if p < 5000:
        return 1
    if p < 20000:
        return 2
    if p < 50000:
        return 3
    if p < 100000:
        return 4
    return 5


def _recency_score(created_at, now) -> float:
    if not created_at:
        return 0.0
    days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    return max(0.0, 1.0 - (days / 90.0))


@transaction.atomic
def rebuild_item_features() -> int:
    now = timezone.now()
    event_aggs = {
        row["item_id"]: row
        for row in InteractionEvent.objects.exclude(item_id=None)
        .values("item_id")
        .annotate(
            views=Count("id", filter=Q(event_type=InteractionEvent.VIEW)),
            clicks=Count("id", filter=Q(event_type=InteractionEvent.CLICK)),
            carts=Count("id", filter=Q(event_type=InteractionEvent.ADD_TO_CART)),
            purchases=Count("id", filter=Q(event_type=InteractionEvent.PURCHASE)),
        )
    }
    order_aggs = {
        row["item_id"]: row["purchases"]
        for row in OrderItem.objects.exclude(item_id=None)
        .values("item_id")
        .annotate(purchases=Count("id"))
    }

    rating_map = {}
    for item in (
        Item.objects.filter(company_id__isnull=False)
        .annotate(avg_rating=Avg("company__reviews__rating"))
        .values("id", "avg_rating")
    ):
        rating_map[item["id"]] = item["avg_rating"]

    count = 0
    for item in Item.objects.all().only(
        "id", "category_obj_id", "price", "created_at", "views"
    ):
        ea = event_aggs.get(item.id, {})
        views = int(ea.get("views") or 0) or int(item.views or 0)
        clicks = int(ea.get("clicks") or 0)
        carts = int(ea.get("carts") or 0)
        purchases = max(int(ea.get("purchases") or 0), int(order_aggs.get(item.id, 0)))
        pop = views * 1.0 + clicks * 2.0 + carts * 4.0 + purchases * 8.0
        ItemFeature.objects.update_or_create(
            item_id=item.id,
            defaults={
                "category_id": item.category_obj_id,
                "view_count": views,
                "click_count": clicks,
                "cart_count": carts,
                "purchase_count": purchases,
                "popularity_score": pop,
                "price_band": _price_band(item.price),
                "recency_score": _recency_score(item.created_at, now),
                "avg_rating": rating_map.get(item.id),
            },
        )
        count += 1
    return count


@transaction.atomic
def rebuild_user_features(days: int = 90) -> int:
    since = timezone.now() - timedelta(days=days)
    events = (
        InteractionEvent.objects.filter(timestamp__gte=since)
        .select_related("item")
        .order_by("-timestamp")
    )

    by_user: dict = defaultdict(list)
    by_session: dict = defaultdict(list)
    for ev in events.iterator(chunk_size=500):
        if ev.user_id:
            by_user[ev.user_id].append(ev)
        elif ev.session_key:
            by_session[ev.session_key].append(ev)

    count = 0

    def _apply(feature: UserFeature, evs: list) -> None:
        affinity: dict[str, float] = {}
        recent: list[int] = []
        views = clicks = carts = purchases = 0
        last_active = None
        for ev in evs:
            last_active = last_active or ev.timestamp
            if ev.event_type == InteractionEvent.VIEW:
                views += 1
            elif ev.event_type == InteractionEvent.CLICK:
                clicks += 1
            elif ev.event_type == InteractionEvent.ADD_TO_CART:
                carts += 1
            elif ev.event_type == InteractionEvent.PURCHASE:
                purchases += 1
            if ev.item_id and ev.item_id not in recent:
                recent.append(ev.item_id)
            cat_id = getattr(ev.item, "category_obj_id", None) if ev.item_id else None
            if cat_id:
                key = str(cat_id)
                weight = {
                    InteractionEvent.VIEW: 1,
                    InteractionEvent.CLICK: 2,
                    InteractionEvent.ADD_TO_CART: 4,
                    InteractionEvent.PURCHASE: 8,
                    InteractionEvent.WATCHLIST: 3,
                }.get(ev.event_type, 1)
                affinity[key] = affinity.get(key, 0.0) + weight
        feature.category_affinity = affinity
        feature.recent_item_ids = recent[:30]
        feature.view_count = views
        feature.click_count = clicks
        feature.cart_count = carts
        feature.purchase_count = purchases
        feature.last_active = last_active
        feature.save()

    for user_id, evs in by_user.items():
        feat, _ = UserFeature.objects.get_or_create(user_id=user_id)
        _apply(feat, evs)
        count += 1

    for session_key, evs in by_session.items():
        feat, _ = UserFeature.objects.get_or_create(
            session_key=session_key, defaults={"user": None}
        )
        _apply(feat, evs)
        count += 1

    # Seed purchase counts from orders for users with little event history
    from customer.models import Order

    for row in (
        Order.objects.values("buyer_id")
        .annotate(c=Count("id"))
        .filter(c__gt=0)
    ):
        feat, _ = UserFeature.objects.get_or_create(user_id=row["buyer_id"])
        if feat.purchase_count < row["c"]:
            feat.purchase_count = row["c"]
            feat.save(update_fields=["purchase_count", "updated_at"])

    return count


@transaction.atomic
def rebuild_item_similarity(max_neighbors: int = 40) -> int:
    """Build co-occurrence similarities from views/purchases in the same session/user."""
    ItemSimilarity.objects.all().delete()

    pairs: dict[tuple[int, int], float] = defaultdict(float)

    def _add_pair_set(item_ids: set[int], weight: float) -> None:
        ids = sorted(i for i in item_ids if i)
        if len(ids) < 2:
            return
        # Cap combinations for huge baskets
        if len(ids) > 25:
            ids = ids[:25]
        for a, b in combinations(ids, 2):
            pairs[(a, b)] += weight
            pairs[(b, a)] += weight

    # Co-view by session
    session_views = defaultdict(set)
    for row in (
        InteractionEvent.objects.filter(
            event_type__in=[InteractionEvent.VIEW, InteractionEvent.CLICK],
            item_id__isnull=False,
        )
        .exclude(session_key="")
        .values_list("session_key", "item_id")
        .iterator(chunk_size=1000)
    ):
        session_views[row[0]].add(row[1])
    for items in session_views.values():
        _add_pair_set(items, 1.0)

    # Co-purchase by order
    order_items = defaultdict(set)
    for row in OrderItem.objects.exclude(item_id=None).values_list("order_id", "item_id"):
        order_items[row[0]].add(row[1])
    for items in order_items.values():
        _add_pair_set(items, 3.0)

    # Co-purchase/view by user
    user_items = defaultdict(set)
    for row in (
        InteractionEvent.objects.filter(
            user_id__isnull=False,
            item_id__isnull=False,
            event_type__in=[
                InteractionEvent.VIEW,
                InteractionEvent.PURCHASE,
                InteractionEvent.ADD_TO_CART,
            ],
        )
        .values_list("user_id", "item_id")
        .iterator(chunk_size=1000)
    ):
        user_items[row[0]].add(row[1])
    for items in user_items.values():
        if len(items) <= 40:
            _add_pair_set(items, 0.5)

    # Keep top neighbors per item
    by_item: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for (a, b), score in pairs.items():
        by_item[a].append((b, score))

    bulk = []
    for item_id, neighbors in by_item.items():
        neighbors.sort(key=lambda x: x[1], reverse=True)
        for similar_id, score in neighbors[:max_neighbors]:
            bulk.append(
                ItemSimilarity(
                    item_id=item_id,
                    similar_item_id=similar_id,
                    score=float(score),
                    source="co_occurrence",
                )
            )
        if len(bulk) >= 500:
            ItemSimilarity.objects.bulk_create(bulk, ignore_conflicts=True)
            bulk = []
    if bulk:
        ItemSimilarity.objects.bulk_create(bulk, ignore_conflicts=True)
    return ItemSimilarity.objects.count()


def rebuild_all_features() -> dict:
    items = rebuild_item_features()
    users = rebuild_user_features()
    sims = rebuild_item_similarity()
    return {"items": items, "users": users, "similarities": sims}
