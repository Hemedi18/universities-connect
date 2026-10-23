import json
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth.models import User
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.utils.html import escape
from django.db.models import Count, Q
from .models import SupportSession, SupportMessage


def _get_or_create_session(request):
    """Retrieve or initialize a support session for a visitor or logged-in user."""
    session_key = request.session.get("support_session_key")
    created = False
    if not session_key:
        session_key = uuid.uuid4().hex
        request.session["support_session_key"] = session_key
        request.session.modified = True

    user = request.user if request.user.is_authenticated else None

    session = SupportSession.objects.filter(session_key=session_key).first()
    if not session:
        guest_name = "Guest"
        guest_email = ""
        if user:
            guest_name = user.get_full_name() or user.username
            guest_email = user.email or ""

        session = SupportSession.objects.create(
            session_key=session_key,
            user=user,
            guest_name=guest_name,
            guest_email=guest_email,
            status="open",
        )
        created = True
    elif user and not session.user:
        session.user = user
        if not session.guest_email and user.email:
            session.guest_email = user.email
        session.save(update_fields=["user", "guest_email", "updated_at"])

    # If new session with no messages, send automatic friendly admin greeting
    if not session.messages.exists():
        admin_user = (
            User.objects.filter(is_superuser=True).first()
            or User.objects.filter(is_staff=True).first()
        )
        SupportMessage.objects.create(
            session=session,
            sender_type="admin",
            sender_user=admin_user,
            text="Hello! Welcome to U-Connect Support. How can we help you with your login, account, or password reset today?",
            is_read=False,
        )

    return session


@never_cache
def guest_chat(request):
    """Guest-facing support chat page (accessible directly from login page)."""
    session = _get_or_create_session(request)

    # Mark admin messages as read when viewed by guest
    session.messages.filter(sender_type="admin", is_read=False).update(is_read=True)

    chat_messages = session.messages.all()

    context = {
        "session": session,
        "chat_messages": chat_messages,
        "is_staff_user": request.user.is_authenticated and request.user.is_staff,
        "guest_name": session.display_name,
        "guest_email": session.guest_email,
        "guest_id": session.session_key,
    }
    return render(request, "users/guest_chat.html", context)


@never_cache
@require_GET
def support_api_messages(request):
    """JSON API to poll for new messages in real time with zero caching."""
    session_id = request.GET.get("session_id")
    session_key = request.GET.get("session_key") or request.session.get("support_session_key")
    after_id = request.GET.get("after_id", 0)
    is_admin_req = request.GET.get("is_admin") == "true"

    try:
        after_id = int(after_id)
    except (ValueError, TypeError):
        after_id = 0

    is_staff = request.user.is_authenticated and request.user.is_staff

    session = None
    if session_id:
        if is_staff and is_admin_req:
            session = get_object_or_404(SupportSession, id=session_id)
        elif session_key:
            session = SupportSession.objects.filter(id=session_id, session_key=session_key).first()
        if not session:
            session = get_object_or_404(SupportSession, id=session_id)
    elif session_key:
        session = SupportSession.objects.filter(session_key=session_key).first()

    if not session:
        session_key = request.session.get("support_session_key")
        if session_key:
            session = SupportSession.objects.filter(session_key=session_key).first()

    if not session:
        return JsonResponse({"status": "error", "message": "No session active"}, status=400)

    # Retrieve messages newer than after_id
    messages_qs = session.messages.filter(id__gt=after_id).order_by("timestamp")

    # Mark as read
    if is_staff and is_admin_req:
        session.messages.filter(sender_type="guest", is_read=False).update(is_read=True)
    else:
        session.messages.filter(sender_type="admin", is_read=False).update(is_read=True)

    data = []
    for msg in messages_qs:
        sender_name = "Support Admin"
        sender_badge = "Admin Support"
        if msg.sender_type == "admin":
            if msg.sender_user:
                sender_name = msg.sender_user.get_full_name() or msg.sender_user.username
        else:
            sender_name = session.display_name
            sender_badge = "You" if not (is_staff and is_admin_req) else "Guest"

        data.append({
            "id": msg.id,
            "sender_type": msg.sender_type,
            "sender_name": sender_name,
            "sender_badge": sender_badge,
            "text": msg.text,
            "time": msg.timestamp.strftime("%I:%M %p"),
            "is_read": msg.is_read,
        })

    response = JsonResponse({
        "status": "success",
        "session_id": session.id,
        "session_status": session.status,
        "session_status_display": session.get_status_display(),
        "messages": data,
    })
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, private"
    response["Pragma"] = "no-cache"
    return response


@never_cache
@require_POST
def support_api_send(request):
    """JSON/Form API to send a message from either guest or admin."""
    text = ""
    session_id = None
    session_key = None
    guest_name = None
    guest_email = None
    is_admin_flag = None

    if request.content_type == "application/json":
        try:
            body_data = json.loads(request.body.decode("utf-8"))
            text = body_data.get("text", "").strip()
            session_id = body_data.get("session_id")
            session_key = body_data.get("session_key")
            guest_name = body_data.get("guest_name")
            guest_email = body_data.get("guest_email")
            is_admin_flag = body_data.get("is_admin")
        except Exception:
            return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)
    else:
        text = request.POST.get("text", "").strip()
        session_id = request.POST.get("session_id")
        session_key = request.POST.get("session_key")
        guest_name = request.POST.get("guest_name")
        guest_email = request.POST.get("guest_email")
        if "is_admin" in request.POST:
            is_admin_flag = request.POST.get("is_admin") == "true"

    if not text:
        return JsonResponse({"status": "error", "message": "Message text cannot be empty"}, status=400)

    is_staff = request.user.is_authenticated and request.user.is_staff
    explicitly_guest = (is_admin_flag is False or is_admin_flag == "false")
    is_admin_send = is_staff and not explicitly_guest and bool(session_id)


    if is_admin_send:
        if not session_id:
            return JsonResponse({"status": "error", "message": "session_id is required for admin replies"}, status=400)
        session = get_object_or_404(SupportSession, id=session_id)
        sender_type = "admin"
        sender_user = request.user

        # Auto assign and set status
        if not session.assigned_admin:
            session.assigned_admin = request.user
        if session.status == "open":
            session.status = "in_progress"
        session.save(update_fields=["assigned_admin", "status", "updated_at"])
    else:
        session = None
        if not session_key:
            session_key = request.session.get("support_session_key")

        if session_id and session_key:
            session = SupportSession.objects.filter(id=session_id, session_key=session_key).first()
        if not session and session_id:
            session = SupportSession.objects.filter(id=session_id).first()
        if not session and session_key:
            session = SupportSession.objects.filter(session_key=session_key).first()
        if not session:
            session = _get_or_create_session(request)

        sender_type = "guest"
        sender_user = request.user if (request.user.is_authenticated and not request.user.is_staff) else None

        updates = ["updated_at"]
        if guest_name and guest_name.strip():
            session.guest_name = guest_name.strip()[:100]
            updates.append("guest_name")
        if guest_email and guest_email.strip():
            session.guest_email = guest_email.strip()[:254]
            updates.append("guest_email")

        # If session was resolved or closed, guest messaging reopens it
        if session.status in ["resolved", "closed"]:
            session.status = "open"
            updates.append("status")

        session.save(update_fields=updates)

    msg = SupportMessage.objects.create(
        session=session,
        sender_type=sender_type,
        sender_user=sender_user,
        text=text,
        is_read=False,
    )

    sender_name = "Support Admin"
    if sender_type == "admin":
        if sender_user:
            sender_name = sender_user.get_full_name() or sender_user.username
    else:
        sender_name = session.display_name

    return JsonResponse({
        "status": "success",
        "message": {
            "id": msg.id,
            "sender_type": msg.sender_type,
            "sender_name": sender_name,
            "sender_badge": "Admin Support" if sender_type == "admin" else "You",
            "text": msg.text,
            "time": msg.timestamp.strftime("%I:%M %p"),
            "is_read": msg.is_read,
        },
    })


@staff_member_required(login_url="/users/login/")
def admin_support_dashboard(request):
    """Admin console: View all support sessions with filters, unread counts, and metrics."""
    status_filter = request.GET.get("status", "all")
    search_query = request.GET.get("q", "").strip()

    sessions = SupportSession.objects.all().select_related("user", "assigned_admin").prefetch_related("messages")

    if status_filter in ["open", "in_progress", "resolved", "closed"]:
        sessions = sessions.filter(status=status_filter)

    if search_query:
        sessions = sessions.filter(
            Q(guest_name__icontains=search_query)
            | Q(guest_email__icontains=search_query)
            | Q(user__username__icontains=search_query)
            | Q(session_key__icontains=search_query)
            | Q(messages__text__icontains=search_query)
        ).distinct()

    # Metrics
    metrics = {
        "total": SupportSession.objects.count(),
        "open": SupportSession.objects.filter(status="open").count(),
        "in_progress": SupportSession.objects.filter(status="in_progress").count(),
        "resolved": SupportSession.objects.filter(status="resolved").count(),
        "total_unread": SupportMessage.objects.filter(sender_type="guest", is_read=False).count(),
    }

    context = {
        "sessions": sessions,
        "status_filter": status_filter,
        "search_query": search_query,
        "metrics": metrics,
    }
    return render(request, "users/admin_support_dashboard.html", context)


@staff_member_required(login_url="/users/login/")
def admin_support_chat(request, session_id):
    """Admin console: Live responder chat room for a specific guest session."""
    session = get_object_or_404(
        SupportSession.objects.select_related("user", "assigned_admin"),
        id=session_id
    )

    # Auto assign to logged-in admin if unassigned
    if not session.assigned_admin:
        session.assigned_admin = request.user
        session.save(update_fields=["assigned_admin"])

    # Mark guest messages as read
    session.messages.filter(sender_type="guest", is_read=False).update(is_read=True)

    chat_messages = session.messages.all()

    # List recent other sessions for quick navigation sidebar
    recent_sessions = (
        SupportSession.objects.exclude(id=session.id)
        .select_related("user")
        .order_by("-updated_at")[:12]
    )

    # Quick preset answers for fast admin responses
    preset_answers = [
        "Hello! I am reviewing your request. Could you please share your student ID or registered email?",
        "Password reset initiated! Please check your email inbox and spam folder for instructions.",
        "Your account has been verified successfully. You can now log in at the login page.",
        "We have temporarily unlocked your account. Please try logging in again.",
        "Is there anything else we can assist you with today?",
    ]

    context = {
        "session": session,
        "chat_messages": chat_messages,
        "recent_sessions": recent_sessions,
        "preset_answers": preset_answers,
    }
    return render(request, "users/admin_support_chat.html", context)


@staff_member_required(login_url="/users/login/")
@require_POST
def admin_support_update_status(request, session_id):
    """Admin action to update session status (open, in_progress, resolved, closed)."""
    session = get_object_or_404(SupportSession, id=session_id)
    new_status = request.POST.get("status")

    if new_status in ["open", "in_progress", "resolved", "closed"]:
        session.status = new_status
        session.save(update_fields=["status", "updated_at"])

        # Add an internal system message if resolved
        if new_status == "resolved":
            SupportMessage.objects.create(
                session=session,
                sender_type="admin",
                sender_user=request.user,
                text="This support conversation has been marked as resolved by Admin. Feel free to send another message if you need further help!",
                is_read=False,
            )

    if request.headers.get("x-requested-with") == "XMLHttpRequest" or request.content_type == "application/json":
        return JsonResponse({"status": "success", "new_status": session.status, "display": session.get_status_display()})

    return redirect("admin_support_chat", session_id=session.id)
