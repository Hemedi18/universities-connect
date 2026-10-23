from django.urls import path
from . import views

app_name = "management"

urlpatterns = [
    path("", views.dashboard_view, name="dashboard"),
    path("switch-mode/", views.switch_admin_mode, name="switch_mode"),
    # User Management APIs
    path("api/users/", views.api_users_list, name="api_users_list"),
    path("api/users/<int:user_id>/toggle-status/", views.api_user_toggle_status, name="api_user_toggle_status"),
    path("api/users/<int:user_id>/toggle-role/", views.api_user_toggle_role, name="api_user_toggle_role"),
    path("api/users/<int:user_id>/verify-email/", views.api_user_verify_email, name="api_user_verify_email"),
    path("api/users/<int:user_id>/delete/", views.api_user_delete, name="api_user_delete"),
    # Webmail & CRM APIs
    path("api/email/inbox/", views.api_email_inbox, name="api_email_inbox"),
    path("api/email/send/", views.api_email_send, name="api_email_send"),
    path("api/email/templates/", views.api_email_templates, name="api_email_templates"),
    # System Diagnostics & Error Logs APIs
    path("api/logs/", views.api_system_logs, name="api_system_logs"),
    path("api/logs/<int:log_id>/resolve/", views.api_resolve_log, name="api_resolve_log"),
    path("api/logs/resolve-all/", views.api_resolve_all_logs, name="api_resolve_all_logs"),
]
