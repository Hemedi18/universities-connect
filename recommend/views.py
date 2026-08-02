import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from .events import ensure_session_key, log_event
from .models import InteractionEvent
from .services import get_recommendations


ALLOWED_EVENTS = {
    InteractionEvent.VIEW,
    InteractionEvent.CLICK,
    InteractionEvent.ADD_TO_CART,
    InteractionEvent.PURCHASE,
    InteractionEvent.SEARCH,
    InteractionEvent.WATCHLIST,
}


@csrf_exempt
@require_http_methods(["POST"])
def api_events(request):
    """
    POST /api/events
    Body: JSON array of {user_id?, item_id?, event_type, timestamp?, metadata?}
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "[]")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        return JsonResponse({"error": "Expected a JSON array"}, status=400)

    session_key = ensure_session_key(request)
    user = request.user if request.user.is_authenticated else None
    created = 0
    errors = []

    for i, row in enumerate(payload[:100]):
        if not isinstance(row, dict):
            errors.append({"index": i, "error": "not an object"})
            continue
        event_type = (row.get("event_type") or "").strip()
        if event_type not in ALLOWED_EVENTS:
            errors.append({"index": i, "error": f"invalid event_type: {event_type}"})
            continue
        item_id = row.get("item_id")
        try:
            item_id = int(item_id) if item_id is not None else None
        except (TypeError, ValueError):
            errors.append({"index": i, "error": "invalid item_id"})
            continue
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if event_type == InteractionEvent.SEARCH and row.get("query"):
            meta = {**meta, "query": str(row.get("query"))[:200]}
        try:
            log_event(
                event_type=event_type,
                item_id=item_id,
                user=user,
                session_key=session_key,
                metadata=meta,
            )
            created += 1
        except Exception as exc:
            errors.append({"index": i, "error": str(exc)})

    return JsonResponse({"ok": True, "created": created, "errors": errors})


@require_GET
def api_recommendations(request):
    """
    GET /api/recommendations?count=10&session_id=
    """
    try:
        count = int(request.GET.get("count") or 10)
    except (TypeError, ValueError):
        count = 10

    session_id = (request.GET.get("session_id") or "").strip()
    session_key = session_id or ensure_session_key(request)
    user = request.user if request.user.is_authenticated else None

    recs, personalized = get_recommendations(
        user=user,
        session_key=session_key,
        count=count,
    )

    return JsonResponse(
        {
            "user_id": user.id if user else None,
            "session_id": session_key,
            "personalized": personalized,
            "recommendations": [
                {"item_id": r["item_id"], "score": r["score"]} for r in recs
            ],
        }
    )
