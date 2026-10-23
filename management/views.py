import json
import logging
import os
from datetime import timedelta
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import connection
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from business.models import Category, Item
from company.models import Company
from customer.models import Order
from users.models import Profile, SupportMessage, SupportSession
from .models import AdminEmailTemplate, SentEmailLog, SystemErrorLog
from .utils_mail import CPANEL_ACCOUNTS, fetch_account_emails, send_cpanel_email

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# 1. MAIN EXECUTIVE DASHBOARD VIEW
# --------------------------------------------------------------------------

@staff_member_required(login_url="/users/login/")
def dashboard_view(request):
    """
    Renders the modern Executive Admin Command Center with real-time stats,
    trends, user management, CRM/Webmail, error logs, and documentation.
    """
    now = timezone.now()
    fourteen_days_ago = now - timedelta(days=14)

    # 1. Core Platform Metrics
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    staff_count = User.objects.filter(is_staff=True).count()
    verified_users = Profile.objects.filter(is_email_verified=True).count()
    unverified_users = total_users - verified_users

    total_companies = Company.objects.count()
    total_items = Item.objects.count()
    active_items = Item.objects.filter(status="active").count()
    sold_items = Item.objects.filter(status="sold").count()
    total_orders = Order.objects.count()

    # 2. Support & Communication Metrics
    open_tickets = SupportSession.objects.filter(status="open").count()
    in_progress_tickets = SupportSession.objects.filter(status="in_progress").count()
    resolved_tickets = SupportSession.objects.filter(status="resolved").count()
    unresolved_errors = SystemErrorLog.objects.filter(is_resolved=False).count()

    # 3. Trends & Predictive Analytics (Past 14 Days)
    dates_list = [(now - timedelta(days=i)).date() for i in range(13, -1, -1)]
    date_labels = [d.strftime("%b %d") for d in dates_list]

    # Registrations by day
    user_regs = (
        User.objects.filter(date_joined__gte=fourteen_days_ago)
        .extra({"day": "date(date_joined)"})
        .values("day")
        .annotate(cnt=Count("id"))
    )
    user_regs_dict = {str(item["day"]): item["cnt"] for item in user_regs}
    reg_trend_data = [user_regs_dict.get(str(d), 0) for d in dates_list]

    # Items by day
    item_adds = (
        Item.objects.filter(created_at__gte=fourteen_days_ago)
        .extra({"day": "date(created_at)"})
        .values("day")
        .annotate(cnt=Count("id"))
    )
    item_adds_dict = {str(item["day"]): item["cnt"] for item in item_adds}
    item_trend_data = [item_adds_dict.get(str(d), 0) for d in dates_list]

    # Category popularity
    categories = Category.objects.annotate(items_count=Count("items")).order_by("-items_count")[:6]
    cat_labels = [c.name for c in categories]
    cat_counts = [c.items_count for c in categories]

    # Predictive Growth Model: 7-day velocity projection
    recent_7d_users = sum(reg_trend_data[-7:])
    growth_rate = recent_7d_users / 7.0 if recent_7d_users > 0 else 0.5
    projected_next_30d = int(total_users + (growth_rate * 30))

    # 4. System Diagnostics
    db_path = settings.DATABASES["default"].get("NAME", "")
    db_size_mb = 0
    if os.path.exists(str(db_path)):
        db_size_mb = round(os.path.getsize(str(db_path)) / (1024 * 1024), 2)

    # 5. Populate Default Templates if empty
    if not AdminEmailTemplate.objects.exists():
        _create_default_templates(request.user)

    templates = AdminEmailTemplate.objects.all()
    recent_users = User.objects.select_related("profile").order_by("-date_joined")[:8]
    recent_logs = SystemErrorLog.objects.order_by("-created_at")[:10]
    recent_tickets = SupportSession.objects.order_by("-updated_at")[:8]

    context = {
        "total_users": total_users,
        "active_users": active_users,
        "staff_count": staff_count,
        "verified_users": verified_users,
        "unverified_users": unverified_users,
        "total_companies": total_companies,
        "total_items": total_items,
        "active_items": active_items,
        "sold_items": sold_items,
        "total_orders": total_orders,
        "open_tickets": open_tickets,
        "in_progress_tickets": in_progress_tickets,
        "resolved_tickets": resolved_tickets,
        "unresolved_errors": unresolved_errors,
        "date_labels_json": json.dumps(date_labels),
        "reg_trend_json": json.dumps(reg_trend_data),
        "item_trend_json": json.dumps(item_trend_data),
        "cat_labels_json": json.dumps(cat_labels),
        "cat_counts_json": json.dumps(cat_counts),
        "growth_rate_daily": round(growth_rate, 1),
        "projected_next_30d": projected_next_30d,
        "db_size_mb": db_size_mb,
        "cpanel_accounts": CPANEL_ACCOUNTS,
        "templates": templates,
        "recent_users": recent_users,
        "recent_logs": recent_logs,
        "recent_tickets": recent_tickets,
        "live_domain": "uconnect.edusphere.co.tz",
        "current_admin_mode": "managed",
    }

    response = render(request, "management/dashboard.html", context)
    response.set_cookie("admin_mode", "managed", max_age=86400 * 30, path="/")
    return response


@staff_member_required(login_url="/users/login/")
def switch_admin_mode(request):
    """
    Seamless toggle between 'managed' (Executive Command Center)
    and 'normal' (Classic Django Admin) mode.
    """
    from django.shortcuts import redirect
    target_mode = request.GET.get("mode", "managed")
    if target_mode == "normal":
        resp = redirect("/admin/?mode=normal")
        resp.set_cookie("admin_mode", "normal", max_age=86400 * 30, path="/")
        return resp
    else:
        resp = redirect("management:dashboard")
        resp.set_cookie("admin_mode", "managed", max_age=86400 * 30, path="/")
        return resp


def _create_default_templates(user):
    defaults = [
        {
            "name": "Karibu U-Connect (Welcome Student)",
            "category": "welcome",
            "subject": "Karibu U-Connect • Soko Lako Rasmi La Chuo!",
            "html_body": """<p>Habari {{ username }},</p>
<p>Tunakukaribisha rasmi kwenye <strong>U-Connect</strong>, soko kuu linalounganisha wanafunzi na wajasiriamali chuoni kote Tanzania.</p>
<p>Kupitia akaunti yako unaweza:</p>
<ul>
  <li>Kununua vifaa vya masomo, laptop, simu, na mahitaji ya chuo kwa usalama.</li>
  <li>Kufungua duka lako na kuuza bidhaa zako kwa wanafunzi wenzako.</li>
  <li>Kupata msaada wa haraka masaa 24/7 kupitia Live Support Chat.</li>
</ul>
<p><a href="https://uconnect.edusphere.co.tz" style="display:inline-block;padding:10px 20px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold;">Anza Sasa Kwenye Tovuti &rarr;</a></p>
<p>Kila la heri,<br><strong>Timu ya U-Connect</strong></p>""",
        },
        {
            "name": "Uthibitisho wa Muuzaji (Seller Approved)",
            "category": "notification",
            "subject": "Hongera! Duka Lako Limethibitishwa Kwenye U-Connect",
            "html_body": """<p>Habari {{ username }},</p>
<p>Tunayo furaha kukutaarifu kuwa duka na wasifu wako wa uuzaji kwenye <strong>U-Connect</strong> vimethibitishwa rasmi na timu ya usimamizi.</p>
<p>Sasa unaweza kuongeza bidhaa zako zikionekana na alama ya uaminifu (Verified Badge) ili kuvutia wanunuzi wengi zaidi chuoni.</p>
<p><a href="https://uconnect.edusphere.co.tz/business/dashboard/" style="display:inline-block;padding:10px 20px;background:#059669;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold;">Fungua Dashboard ya Muuzaji &rarr;</a></p>
<p>Kila la heri katika biashara yako,<br><strong>U-Connect Business Team</strong></p>""",
        },
        {
            "name": "Msaada na Upatanishi (Dispute & Support Resolution)",
            "category": "support",
            "subject": "U-Connect Support: Majibu ya Tiketi Yako ya Msaada",
            "html_body": """<p>Habari {{ username }},</p>
<p>Tumepokea na kufanyia kazi maoni yako kuhusu agizo au huduma uliyoomba msaada.</p>
<p>Tafadhali ingia kwenye mfumo na ufungue Live Support Chat ili kupata ufafanuzi zaidi au kuthibitisha utatuzi wa suala lako.</p>
<p><a href="https://uconnect.edusphere.co.tz/support-chat/" style="display:inline-block;padding:10px 20px;background:#4f46e5;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold;">Fungua Support Chat &rarr;</a></p>
<p>Tupo hapa kukuhudumia daima,<br><strong>U-Connect Customer Support</strong></p>""",
        },
        {
            "name": "Tahadhari ya Usalama (Security Notice)",
            "category": "security",
            "subject": "Tahadhari Muhimu ya Usalama wa Akaunti Yako",
            "html_body": """<p>Habari {{ username }},</p>
<p>Tumebaini jaribio la kubadilisha nenosiri au kuingia kwenye akaunti yako kutoka kwenye kifaa kisichofahamika.</p>
<p>Ikiwa ulikuwa ni wewe, unaweza kupuuza ujumbe huu. Kama hukufanya ombi hili, tafadhali badilisha nenosiri lako haraka:</p>
<p><a href="https://uconnect.edusphere.co.tz/password-reset/" style="display:inline-block;padding:10px 20px;background:#dc2626;color:#fff;text-decoration:none;border-radius:8px;font-weight:bold;">Badilisha Nenosiri Sasa &rarr;</a></p>
<p>Usalama wako ni kipaumbele chetu,<br><strong>U-Connect Security Team</strong></p>""",
        },
    ]

    for item in defaults:
        AdminEmailTemplate.objects.get_or_create(
            name=item["name"],
            defaults={
                "category": item["category"],
                "subject": item["subject"],
                "html_body": item["html_body"],
                "created_by": user,
            },
        )


# --------------------------------------------------------------------------
# 2. USER MANAGEMENT API ENDPOINTS
# --------------------------------------------------------------------------

@staff_member_required
@require_http_methods(["GET"])
def api_users_list(request):
    """
    Search and filter users by query, role, verification status, and pagination.
    """
    q = request.GET.get("q", "").strip()
    role_filter = request.GET.get("role", "all")
    page_num = int(request.GET.get("page", 1))

    qs = User.objects.select_related("profile").prefetch_related("item_set", "orders").order_by("-date_joined")

    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(profile__phone_number__icontains=q)
        )

    if role_filter == "staff":
        qs = qs.filter(is_staff=True)
    elif role_filter == "superuser":
        qs = qs.filter(is_superuser=True)
    elif role_filter == "sellers":
        qs = qs.filter(item_set__isnull=False).distinct()
    elif role_filter == "buyers":
        qs = qs.filter(orders__isnull=False).distinct()
    elif role_filter == "unverified":
        qs = qs.filter(Q(profile__is_email_verified=False) | Q(profile__isnull=True))
    elif role_filter == "inactive":
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(page_num)

    results = []
    for u in page_obj:
        phone = getattr(u, "profile", None).phone_number if hasattr(u, "profile") else ""
        verified = getattr(u, "profile", None).is_email_verified if hasattr(u, "profile") else False
        results.append({
            "id": u.id,
            "username": u.username,
            "email": u.email or "—",
            "full_name": f"{u.first_name} {u.last_name}".strip() or "—",
            "phone": phone or "—",
            "is_active": u.is_active,
            "is_staff": u.is_staff,
            "is_superuser": u.is_superuser,
            "is_verified": verified,
            "items_count": u.item_set.count(),
            "orders_count": u.orders.count(),
            "date_joined": u.date_joined.strftime("%Y-%m-%d %H:%M"),
        })

    return JsonResponse({
        "status": "success",
        "users": results,
        "total_count": paginator.count,
        "total_pages": paginator.num_pages,
        "current_page": page_obj.number,
        "has_next": page_obj.has_next(),
        "has_previous": page_obj.has_previous(),
    })


@staff_member_required
@require_http_methods(["POST"])
def api_user_toggle_status(request, user_id):
    """Toggle user active / suspended status."""
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        return JsonResponse({"status": "error", "message": "Huwezi kujifungia mwenyewe!"}, status=400)

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=["is_active"])

    action = "kufunguliwa" if target_user.is_active else "kufungiwa"
    return JsonResponse({
        "status": "success",
        "is_active": target_user.is_active,
        "message": f"Mtumiaji {target_user.username} amefanikiwa {action}.",
    })


@staff_member_required
@require_http_methods(["POST"])
def api_user_toggle_role(request, user_id):
    """Toggle staff / superuser privilege."""
    target_user = get_object_or_404(User, id=user_id)
    role_type = request.POST.get("role_type", "staff")

    if target_user == request.user and not target_user.is_superuser:
        return JsonResponse({"status": "error", "message": "Huwezi kubadilisha mamlaka yako mwenyewe!"}, status=400)

    if role_type == "staff":
        target_user.is_staff = not target_user.is_staff
        target_user.save(update_fields=["is_staff"])
        val = target_user.is_staff
    elif role_type == "superuser":
        if not request.user.is_superuser:
            return JsonResponse({"status": "error", "message": "Superuser pekee ndiye anayeweza kutoa mamlaka ya Superuser!"}, status=403)
        target_user.is_superuser = not target_user.is_superuser
        if target_user.is_superuser:
            target_user.is_staff = True
            target_user.save(update_fields=["is_superuser", "is_staff"])
        else:
            target_user.save(update_fields=["is_superuser"])
        val = target_user.is_superuser
    else:
        return JsonResponse({"status": "error", "message": "Role haitambaliki"}, status=400)

    return JsonResponse({
        "status": "success",
        "new_value": val,
        "message": f"Mamlaka ya {target_user.username} yamesasishwa kikamilifu.",
    })


@staff_member_required
@require_http_methods(["POST"])
def api_user_verify_email(request, user_id):
    """Manually verify user's email address."""
    target_user = get_object_or_404(User, id=user_id)
    profile, _ = Profile.objects.get_or_create(user=target_user)
    profile.is_email_verified = True
    profile.save(update_fields=["is_email_verified"])
    target_user.is_active = True
    target_user.save(update_fields=["is_active"])

    return JsonResponse({
        "status": "success",
        "message": f"Barua pepe ya {target_user.username} imethibitishwa.",
    })


@staff_member_required
@require_http_methods(["POST"])
def api_user_delete(request, user_id):
    """Safely delete a user account with verification."""
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        return JsonResponse({"status": "error", "message": "Huwezi kufuta akaunti unayotumia sasa!"}, status=400)

    if target_user.is_superuser and not request.user.is_superuser:
        return JsonResponse({"status": "error", "message": "Huna mamlaka ya kufuta Superuser!"}, status=403)

    uname = target_user.username
    target_user.delete()
    return JsonResponse({
        "status": "success",
        "message": f"Akaunti ya {uname} imefutwa kabisa kutoka kwenye mfumo.",
    })


# --------------------------------------------------------------------------
# 3. WEBMAIL & CRM EMAIL API ENDPOINTS (cPanel Live Integration)
# --------------------------------------------------------------------------

@staff_member_required
@require_http_methods(["GET"])
def api_email_inbox(request):
    """Fetch live emails from cPanel via IMAP SSL."""
    account_key = request.GET.get("account", "support")
    folder = request.GET.get("folder", "INBOX")
    limit = int(request.GET.get("limit", 15))

    data = fetch_account_emails(account_key=account_key, folder=folder, limit=limit)
    return JsonResponse(data)


@staff_member_required
@require_http_methods(["POST"])
def api_email_send(request):
    """
    Send an outgoing email using any of the 4 cPanel accounts via SMTP SSL
    and record the transaction in SentEmailLog.
    """
    account_key = request.POST.get("account", "support")
    to_email = request.POST.get("to_email", "").strip()
    subject = request.POST.get("subject", "").strip()
    body_html = request.POST.get("body_html", "").strip()
    template_id = request.POST.get("template_id")

    if not to_email or not subject or not body_html:
        return JsonResponse({"status": "error", "message": "Tafadhali jaza taarifa zote muhimu (To, Subject, Message)."}, status=400)

    # Wrap in master template if not already a full document
    if "<html" not in body_html.lower():
        from django.template.loader import render_to_string
        try:
            body_html = render_to_string("emails/base_email.html", {
                "subject": subject,
                "content": body_html,
            })
        except Exception:
            pass

    success, msg = send_cpanel_email(
        account_key=account_key,
        to_email=to_email,
        subject=subject,
        body_html=body_html,
    )

    template_obj = None
    if template_id:
        template_obj = AdminEmailTemplate.objects.filter(id=template_id).first()

    account_email = CPANEL_ACCOUNTS.get(account_key, {}).get("email", "")

    SentEmailLog.objects.create(
        sender_email=account_email,
        recipient_email=to_email,
        subject=subject,
        body=body_html[:3000],
        template=template_obj,
        status="sent" if success else "failed",
        error_message=None if success else msg,
        sent_by=request.user,
    )

    if success:
        return JsonResponse({"status": "success", "message": f"Barua pepe imetumwa kwa {to_email} kupitia {account_email}."})
    else:
        return JsonResponse({"status": "error", "message": f"Hitilafu ya kutuma: {msg}"}, status=500)


@staff_member_required
@require_http_methods(["GET", "POST"])
def api_email_templates(request):
    """List or create email templates."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        category = request.POST.get("category", "support")
        subject = request.POST.get("subject", "").strip()
        html_body = request.POST.get("html_body", "").strip()

        if not name or not subject or not html_body:
            return JsonResponse({"status": "error", "message": "Jaza jina, mada, na maudhui ya kiolezo."}, status=400)

        tmpl = AdminEmailTemplate.objects.create(
            name=name,
            category=category,
            subject=subject,
            html_body=html_body,
            created_by=request.user,
        )
        return JsonResponse({"status": "success", "id": tmpl.id, "name": tmpl.name})

    templates = AdminEmailTemplate.objects.all()
    results = [
        {
            "id": t.id,
            "name": t.name,
            "category": t.category,
            "category_display": t.get_category_display(),
            "subject": t.subject,
            "html_body": t.html_body,
        }
        for t in templates
    ]
    return JsonResponse({"status": "success", "templates": results})


# --------------------------------------------------------------------------
# 4. SYSTEM HEALTH & ERROR LOGS API
# --------------------------------------------------------------------------

@staff_member_required
@require_http_methods(["GET"])
def api_system_logs(request):
    """Retrieve error logs with level filtering."""
    level = request.GET.get("level", "all")
    unresolved_only = request.GET.get("unresolved_only", "false") == "true"

    qs = SystemErrorLog.objects.all()
    if level != "all":
        qs = qs.filter(level=level)
    if unresolved_only:
        qs = qs.filter(is_resolved=False)

    logs = qs[:50]
    results = [
        {
            "id": l.id,
            "level": l.level,
            "message": l.message,
            "endpoint": l.endpoint or "—",
            "ip_address": l.ip_address or "—",
            "user": l.user.username if l.user else "Anonymous",
            "is_resolved": l.is_resolved,
            "traceback": l.traceback or "",
            "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for l in logs
    ]
    return JsonResponse({"status": "success", "logs": results})


@staff_member_required
@require_http_methods(["POST"])
def api_resolve_log(request, log_id):
    """Mark an error log as resolved."""
    log_item = get_object_or_404(SystemErrorLog, id=log_id)
    log_item.is_resolved = True
    log_item.resolved_by = request.user
    log_item.save(update_fields=["is_resolved", "resolved_by"])
    return JsonResponse({"status": "success", "message": "Log imewekwa alama ya kutatuliwa."})


@staff_member_required
@require_http_methods(["POST"])
def api_resolve_all_logs(request):
    """Mark all unresolved error logs as resolved."""
    count = SystemErrorLog.objects.filter(is_resolved=False).update(
        is_resolved=True, resolved_by=request.user
    )
    return JsonResponse({"status": "success", "message": f"Kumbukumbu {count} zimewekwa alama ya kutatuliwa."})
