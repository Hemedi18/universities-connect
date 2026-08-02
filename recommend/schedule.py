"""Auto-rebuild recommendation features when they go stale.

Triggered lazily from recommendation requests (no Celery required).
Uses a cache lock so only one rebuild runs at a time.
"""

from __future__ import annotations

import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max
from django.utils import timezone

logger = logging.getLogger(__name__)

LAST_REBUILD_CACHE_KEY = "rec:rebuild:last_ts"
REBUILD_LOCK_KEY = "rec:rebuild:lock"
DEFAULT_INTERVAL_SECONDS = 6 * 60 * 60  # 6 hours


def rebuild_interval_seconds() -> int:
    return int(
        getattr(settings, "RECOMMEND_REBUILD_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)
    )


def auto_rebuild_enabled() -> bool:
    return bool(getattr(settings, "RECOMMEND_REBUILD_ON_REQUEST", True))


def last_rebuild_at():
    """Return timezone-aware datetime of last successful rebuild, or None."""
    cached = cache.get(LAST_REBUILD_CACHE_KEY)
    if cached:
        try:
            return timezone.datetime.fromtimestamp(float(cached), tz=timezone.get_current_timezone())
        except (TypeError, ValueError, OSError):
            pass
    from .models import ItemFeature

    latest = ItemFeature.objects.aggregate(m=Max("updated_at"))["m"]
    return latest


def features_are_stale() -> bool:
    interval = rebuild_interval_seconds()
    if interval <= 0:
        return False
    latest = last_rebuild_at()
    if latest is None:
        return True
    return timezone.now() - latest >= timedelta(seconds=interval)


def mark_rebuild_complete() -> None:
    cache.set(LAST_REBUILD_CACHE_KEY, timezone.now().timestamp(), None)


def _run_rebuild() -> None:
    from django.db import close_old_connections

    close_old_connections()
    try:
        from .features import rebuild_all_features

        stats = rebuild_all_features()
        mark_rebuild_complete()
        logger.info(
            "Auto-rebuilt recommend features: items=%s users=%s similarities=%s",
            stats.get("items"),
            stats.get("users"),
            stats.get("similarities"),
        )
    except Exception:
        logger.exception("Auto rebuild of recommend features failed")
    finally:
        cache.delete(REBUILD_LOCK_KEY)
        close_old_connections()


def maybe_rebuild_features(*, force: bool = False, async_mode: bool = True) -> bool:
    """
    If features are older than RECOMMEND_REBUILD_INTERVAL_SECONDS, rebuild.
    Returns True if a rebuild was started (or completed synchronously).
    """
    if not auto_rebuild_enabled() and not force:
        return False
    if not force and not features_are_stale():
        return False

    # Lock TTL covers a slow rebuild; only one worker rebuilds.
    lock_ttl = max(300, min(rebuild_interval_seconds(), 3600))
    if not cache.add(REBUILD_LOCK_KEY, "1", timeout=lock_ttl):
        return False

    if async_mode:
        thread = threading.Thread(
            target=_run_rebuild,
            name="recommend-feature-rebuild",
            daemon=True,
        )
        thread.start()
        return True

    _run_rebuild()
    return True
