from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone

from business.models import Item

from .models import ItemFeature, UserFeature
from .retrieve import retrieve_candidates


CACHE_TTL = 60


def _load_user_feature(user=None, session_key: str = "") -> UserFeature | None:
    if user and getattr(user, "is_authenticated", False):
        return UserFeature.objects.filter(user=user).first()
    if session_key:
        return UserFeature.objects.filter(session_key=session_key, user__isnull=True).first()
    return None


def _cache_key(user=None, session_key: str = "", n: int = 10, seed_item_id=None) -> str:
    uid = getattr(user, "id", None) or "anon"
    sid = session_key or "-"
    seed = seed_item_id or 0
    return f"rec:v1:{uid}:{sid}:{n}:{seed}"


def rank_candidates(
    *,
    candidates: list[dict],
    user=None,
    session_key: str = "",
    n: int = 10,
    exclude_ids: set[int] | None = None,
) -> list[dict]:
    """
    Weighted linear ranker with light diversity (category cap).
    Returns [{"item_id", "score"}, ...]
    """
    exclude_ids = set(exclude_ids or [])
    uf = _load_user_feature(user, session_key)
    recent = set((uf.recent_item_ids if uf else None) or [])
    affinity = dict((uf.category_affinity if uf else None) or {})

    item_ids = [c["item_id"] for c in candidates if c["item_id"] not in exclude_ids]
    if not item_ids:
        return []

    features = {
        f.item_id: f
        for f in ItemFeature.objects.filter(item_id__in=item_ids)
    }
    items = {
        i.id: i
        for i in Item.objects.filter(id__in=item_ids).only(
            "id", "category_obj_id", "created_at", "views", "stock_quantity", "status"
        )
    }

    scored = []
    for c in candidates:
        iid = c["item_id"]
        if iid in exclude_ids:
            continue
        item = items.get(iid)
        if not item or item.status != "active" or (item.stock_quantity or 0) <= 0:
            continue
        feat = features.get(iid)
        pop = float(feat.popularity_score) if feat else float(item.views or 0)
        recency = float(feat.recency_score) if feat else 0.0
        cat_id = (feat.category_id if feat else None) or item.category_obj_id
        aff = float(affinity.get(str(cat_id), 0.0)) if cat_id else 0.0
        seen_penalty = 4.0 if iid in recent else 0.0
        source = float(c.get("source_score") or 0.0)
        score = (
            0.45 * source
            + 0.25 * (pop ** 0.5)
            + 0.20 * (aff + 1.0)
            + 0.15 * (recency * 10.0)
            - seen_penalty
        )
        scored.append(
            {
                "item_id": iid,
                "score": score,
                "category_id": cat_id,
                "sources": c.get("sources") or set(),
            }
        )

    scored.sort(key=lambda r: r["score"], reverse=True)

    # Diversity: at most 3 from same category in top-N
    picked: list[dict] = []
    cat_counts: dict[int, int] = {}
    for row in scored:
        cat = row["category_id"] or 0
        if cat_counts.get(cat, 0) >= 3 and len(picked) < n:
            continue
        picked.append({"item_id": row["item_id"], "score": round(row["score"], 4)})
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if len(picked) >= n:
            break

    # If diversity filtered too hard, fill from remaining
    if len(picked) < n:
        have = {p["item_id"] for p in picked}
        for row in scored:
            if row["item_id"] in have:
                continue
            picked.append({"item_id": row["item_id"], "score": round(row["score"], 4)})
            if len(picked) >= n:
                break

    return picked


def popularity_fallback(n: int = 10, exclude_ids: set[int] | None = None, user=None) -> list[dict]:
    exclude_ids = set(exclude_ids or [])
    qs = Item.objects.filter(status="active", stock_quantity__gt=0)
    if user and getattr(user, "is_authenticated", False):
        qs = qs.exclude(seller=user)
    qs = qs.exclude(id__in=exclude_ids)

    # Prefer ItemFeature popularity; mix newest
    feat_ids = list(
        ItemFeature.objects.filter(item_id__in=qs.values("id"))
        .order_by("-popularity_score")
        .values_list("item_id", flat=True)[: n]
    )
    if len(feat_ids) < n:
        extra = list(
            qs.order_by("-views", "-created_at")
            .exclude(id__in=feat_ids)
            .values_list("id", flat=True)[: n - len(feat_ids)]
        )
        feat_ids.extend(extra)

    # Inject a couple of newest for cold start freshness
    newest = list(
        qs.order_by("-created_at")
        .exclude(id__in=feat_ids)
        .values_list("id", flat=True)[: max(2, n // 5)]
    )
    merged = []
    for iid in feat_ids + newest:
        if iid not in merged:
            merged.append(iid)
        if len(merged) >= n:
            break
    return [{"item_id": iid, "score": float(n - i)} for i, iid in enumerate(merged)]


def get_recommendations(
    request=None,
    *,
    user=None,
    session_key: str = "",
    count: int = 10,
    seed_item_id: int | None = None,
    exclude_ids: set[int] | None = None,
    use_cache: bool = True,
) -> tuple[list[dict], bool]:
    """
    Full retrieve → rank pipeline.
    Returns (recommendations, personalized).
    """
    # Lazily refresh feature store when stale (background thread).
    try:
        from .schedule import maybe_rebuild_features

        maybe_rebuild_features(async_mode=True)
    except Exception:
        pass

    if request is not None:
        from .events import ensure_session_key

        user = request.user if getattr(request.user, "is_authenticated", False) else None
        session_key = session_key or ensure_session_key(request)

    count = max(1, min(int(count or 10), 50))
    exclude_ids = set(exclude_ids or [])
    if seed_item_id:
        exclude_ids.add(seed_item_id)

    cache_key = _cache_key(user, session_key, count, seed_item_id)
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached["recs"], cached["personalized"]

    personalized = False
    try:
        uf = _load_user_feature(user, session_key)
        has_signal = bool(
            uf
            and (
                uf.recent_item_ids
                or uf.category_affinity
                or uf.purchase_count
                or uf.view_count
            )
        )
        if user and getattr(user, "is_authenticated", False):
            try:
                if user.profile.watchlist.exists():
                    has_signal = True
            except Exception:
                pass

        candidates = retrieve_candidates(
            user=user,
            session_key=session_key,
            k=max(200, count * 15),
            seed_item_id=seed_item_id,
        )
        recs = rank_candidates(
            candidates=candidates,
            user=user,
            session_key=session_key,
            n=count,
            exclude_ids=exclude_ids,
        )
        personalized = has_signal and bool(recs)
        if not recs:
            recs = popularity_fallback(count, exclude_ids, user=user)
            personalized = False
    except Exception:
        recs = popularity_fallback(count, exclude_ids, user=user)
        personalized = False

    if use_cache:
        cache.set(
            cache_key,
            {"recs": recs, "personalized": personalized},
            CACHE_TTL,
        )
    return recs, personalized


def recommendations_as_items(recs: list[dict], annotate: bool = True):
    """Preserve recommendation order as Item queryset list."""
    from django.db.models import Avg, Count

    ids = [r["item_id"] for r in recs]
    if not ids:
        return []
    qs = Item.objects.filter(id__in=ids, status="active").select_related(
        "category_obj", "company", "seller"
    )
    if annotate:
        qs = qs.annotate(
            avg_rating=Avg("company__reviews__rating"),
            review_count=Count("company__reviews", distinct=True),
        )
    by_id = {i.id: i for i in qs}
    return [by_id[i] for i in ids if i in by_id]
