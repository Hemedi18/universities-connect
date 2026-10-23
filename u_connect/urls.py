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
    return render(
        request,
        "pwa/serviceworker.js",
        content_type="application/javascript",
    )

from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "favicon.ico",
        RedirectView.as_view(url="/static/images/uconnect.ico", permanent=True),
    ),
    path("serviceworker.js", service_worker, name="serviceworker"),
    path("", include("recommend.urls")),
    path("", include("customer.urls")),
    path("business/", include("business.urls")),
    path("users/", include("users.urls")),
    path("chat/", include("chat.urls")),
    path("company/", include("company.urls")),
    path("management/", include("management.urls")),
    path("", include("pwa.urls")),
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

