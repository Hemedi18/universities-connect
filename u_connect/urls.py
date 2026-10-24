"""
URL configuration for u_connect project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from users.views_password import (
    request_password_reset,
    verify_password_reset,
    resend_password_reset_otp,
)
from users import views_support

from django.shortcuts import render

def service_worker(request):
    response = render(
        request,
        "pwa/serviceworker.js",
        content_type="application/javascript",
    )
    response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response

from django.shortcuts import redirect
from django.views.generic import RedirectView
from django.utils.translation import activate
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme


def set_language_view(request, lang_code):
    """
    Direct language switcher endpoint allowing users to switch easily to
    English ('en'), Swahili ('sw'), or Arabic ('ar'). Sets the language
    cookie, updates the session, and redirects back to the previous page.
    """
    lang_code = (lang_code or "").lower()
    valid_codes = [code for code, _name in getattr(settings, "LANGUAGES", [])]
    if lang_code not in valid_codes:
        lang_code = getattr(settings, "LANGUAGE_CODE", "en")

    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or "/"
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = "/"

    response = HttpResponseRedirect(next_url)
    cookie_name = getattr(settings, "LANGUAGE_COOKIE_NAME", "django_language")
    cookie_age = getattr(settings, "LANGUAGE_COOKIE_AGE", 86400 * 365)
    cookie_path = getattr(settings, "LANGUAGE_COOKIE_PATH", "/")
    response.set_cookie(
        cookie_name,
        lang_code,
        max_age=cookie_age,
        path=cookie_path,
        samesite="Lax",
    )
    if hasattr(request, "session"):
        request.session[cookie_name] = lang_code
    activate(lang_code)
    return response

def admin_mode_router(request):
    """
    Route admin landing:
    By default, opens Management Mode (/management/).
    If ?mode=normal or cookie admin_mode=normal, opens Classic Django Admin (Normal Mode).
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        return admin.site.login(request)

    mode = request.GET.get("mode")
    cookie_mode = request.COOKIES.get("admin_mode")

    if mode == "normal" or (not mode and cookie_mode == "normal"):
        resp = admin.site.index(request)
        resp.set_cookie("admin_mode", "normal", max_age=86400 * 30, path="/")
        return resp

    # Default to Management Mode
    resp = redirect("management:dashboard")
    resp.set_cookie("admin_mode", "managed", max_age=86400 * 30, path="/")
    return resp

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("set-language/<str:lang_code>/", set_language_view, name="set_language_direct"),
    path("admin/", admin_mode_router, name="admin_mode_router"),
    path("admin/", admin.site.urls),
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/images/uconnect.ico", permanent=True),
    ),
    path("serviceworker.js", service_worker, name="serviceworker"),
    path("", include("recommend.urls")),
    path("", include("customer.urls")),
    path("customer/", include("customer.urls", namespace="customer_alt")),
    path("business/", include("business.urls")),
    path("users/", include("users.urls")),
    path("chat/", include("chat.urls")),
    path("company/", include("company.urls")),
    path("management/", include("management.urls")),
    path("", include("pwa.urls")),
    path("sell/", RedirectView.as_view(url="/business/sell/", permanent=False)),
    path("post-item/", RedirectView.as_view(url="/business/sell/", permanent=False)),
    path("password-reset/", request_password_reset, name="password_reset_request"),
    path("password-reset/verify/", verify_password_reset, name="password_reset_verify"),
    path("password-reset/resend/", resend_password_reset_otp, name="password_reset_resend"),
    # Support Chat (Guest & Login Assistance)
    path("support-chat/", views_support.guest_chat, name="guest_chat"),
    path("support-chat/api/messages/", views_support.support_api_messages, name="support_api_messages"),
    path("support-chat/api/send/", views_support.support_api_send, name="support_api_send"),
    path("support-chat/manage/", views_support.admin_support_dashboard, name="admin_support_dashboard"),
    path("support-chat/manage/<int:session_id>/", views_support.admin_support_chat, name="admin_support_chat"),
    path("support-chat/manage/<int:session_id>/status/", views_support.admin_support_update_status, name="admin_support_update_status"),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

