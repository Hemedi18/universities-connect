from __future__ import annotations

from business.models import Item

from .models import InteractionEvent, ItemFeature, ItemSimilarity, UserFeature


def _load_user_feature(user=None, session_key: str = "") -> UserFeature | None:
    if user and getattr(user, "is_authenticated", False):
        return UserFeature.objects.filter(user=user).first()
    if session_key:
        return UserFeature.objects.filter(session_key=session_key, user__isnull=True).first()
    return None


def _exclude_own_and_invalid(qs, user=None):
    qs = qs.filter(status="active", stock_quantity__gt=0)
    if user and getattr(user, "is_authenticated", False):
        qs = qs.exclude(seller=user)
    return qs


def retrieve_candidates(
    *,
    user=None,
    session_key: str = "",
    k: int = 200,
    seed_item_id: int | None = None,
) -> list[dict]:
    """
    High-recall candidate union.
    Returns list of {"item_id": int, "source_score": float, "sources": set[str]}.
    """
    scores: dict[int, dict] = {}

    def add(item_id: int, score: float, source: str) -> None:
        if not item_id:
            return
        row = scores.get(item_id)
        if not row:
            scores[item_id] = {"item_id": item_id, "source_score": score, "sources": {source}}
        else:
            row["source_score"] = max(row["source_score"], score)
            row["sources"].add(source)

    # 1) Popularity
    for feat in ItemFeature.objects.order_by("-popularity_score")[: max(k // 2, 50)]:
        add(feat.item_id, float(feat.popularity_score) + 0.01, "popularity")

    # Fallback popularity from Item.views if features empty
    if not scores:
        for item_id in (
            Item.objects.filter(status="active", stock_quantity__gt=0)
            .order_by("-views", "-created_at")
            .values_list("id", flat=True)[: max(k // 2, 50)]
        ):
            add(item_id, 1.0, "popularity")

    uf = _load_user_feature(user, session_key)
    recent_ids: list[int] = list((uf.recent_item_ids if uf else None) or [])
    affinity = dict((uf.category_affinity if uf else None) or {})

    if seed_item_id and seed_item_id not in recent_ids:
        recent_ids = [seed_item_id] + recent_ids

    # 2) Collaborative: item–item similarity from recent items
    seed_for_sim = recent_ids[:10] or ([seed_item_id] if seed_item_id else [])
    if seed_for_sim:
        for sim in (
            ItemSimilarity.objects.filter(item_id__in=seed_for_sim)
            .order_by("-score")[:k]
        ):
            add(sim.similar_item_id, float(sim.score) * 10.0, "collaborative")

    # 3) Content / category affinity
    top_cats = sorted(affinity.items(), key=lambda x: x[1], reverse=True)[:5]
    cat_ids = [int(c) for c, _ in top_cats if str(c).isdigit()]
    if not cat_ids and seed_item_id:
        cat = (
            Item.objects.filter(pk=seed_item_id)
            .values_list("category_obj_id", flat=True)
            .first()
        )
        if cat:
            cat_ids = [cat]
    if cat_ids:
        for item_id, cat_id in (
            Item.objects.filter(
                status="active",
                stock_quantity__gt=0,
                category_obj_id__in=cat_ids,
            )
            .order_by("-views", "-created_at")
            .values_list("id", "category_obj_id")[: max(k // 2, 40)]
        ):
            aff = float(affinity.get(str(cat_id), 1.0))
            add(item_id, 5.0 + aff, "category")

    # 4) Direct signals: watchlist + purchase history categories
    if user and getattr(user, "is_authenticated", False):
        try:
            watch_ids = list(
                user.profile.watchlist.filter(status="active").values_list("id", flat=True)[:30]
            )
            for wid in watch_ids:
                add(wid, 20.0, "watchlist")
                for sim in ItemSimilarity.objects.filter(item_id=wid).order_by("-score")[:15]:
                    add(sim.similar_item_id, float(sim.score) * 8.0, "watchlist_sim")
        except Exception:
            pass

        from customer.models import OrderItem

        purchased_cats = set(
            OrderItem.objects.filter(order__buyer=user, item__isnull=False)
            .values_list("item__category_obj_id", flat=True)
            .distinct()[:10]
        )
        purchased_cats.discard(None)
        if purchased_cats:
            for item_id in (
                Item.objects.filter(
                    status="active",
                    stock_quantity__gt=0,
                    category_obj_id__in=purchased_cats,
                )
                .order_by("-created_at")
                .values_list("id", flat=True)[:40]
            ):
                add(item_id, 8.0, "purchase_category")

    # Filter invalid / own listings
    if not scores:
        return []

    valid_ids = set(
        _exclude_own_and_invalid(
            Item.objects.filter(id__in=list(scores.keys())),
            user=user,
        ).values_list("id", flat=True)
    )
    # Don't recommend already owned / just-purchased as primary? keep them filtered only if OOS

    candidates = [scores[i] for i in valid_ids if i in scores]
    # Exclude seed item from related-style lists optionally handled by caller
    candidates.sort(key=lambda r: r["source_score"], reverse=True)
    return candidates[:k]
