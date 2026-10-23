from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import PasswordResetRequest, SupportSession, SupportMessage

# Register your models here.


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "created_at", "is_resolved")
    list_filter = ("is_resolved", "created_at")
    actions = ["mark_as_resolved"]

    def mark_as_resolved(self, request, queryset):
        queryset.update(is_resolved=True)


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 1
    fields = ("sender_type", "sender_user", "text", "is_read", "timestamp")
    readonly_fields = ("timestamp",)


@admin.register(SupportSession)
class SupportSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "display_name_column",
        "guest_email",
        "status",
        "assigned_admin",
        "unread_admin_badge",
        "updated_at",
        "live_chat_link",
    )
    list_filter = ("status", "created_at", "assigned_admin")
    search_fields = (
        "guest_name",
        "guest_email",
        "user__username",
        "session_key",
        "messages__text",
    )
    readonly_fields = ("created_at", "updated_at", "session_key", "live_chat_link")
    inlines = [SupportMessageInline]
    actions = ["mark_as_resolved", "mark_as_open", "assign_to_me"]

    def display_name_column(self, obj):
        return obj.display_name
    display_name_column.short_description = "User / Guest"

    def unread_admin_badge(self, obj):
        count = obj.unread_count_for_admin
        if count > 0:
            return format_html(
                '<span style="background:#dc3545;color:white;padding:2px 8px;border-radius:10px;font-weight:bold;">{} new</span>',
                count,
            )
        return format_html('<span style="color:#6c757d;">0</span>')
    unread_admin_badge.short_description = "Unread"

    def live_chat_link(self, obj):
        url = reverse("admin_support_chat", args=[obj.id])
        return format_html(
            '<a class="button" style="background:#0d6efd;color:white;padding:4px 10px;border-radius:4px;text-decoration:none;" href="{}">Open Console</a>',
            url,
        )
    live_chat_link.short_description = "Live Console"

    def mark_as_resolved(self, request, queryset):
        queryset.update(status="resolved")
    mark_as_resolved.short_description = "Mark selected as Resolved"

    def mark_as_open(self, request, queryset):
        queryset.update(status="open")
    mark_as_open.short_description = "Mark selected as Open"

    def assign_to_me(self, request, queryset):
        queryset.update(assigned_admin=request.user)
    assign_to_me.short_description = "Assign selected to me"


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "sender_type", "sender_user", "text_snippet", "timestamp", "is_read")
    list_filter = ("sender_type", "is_read", "timestamp")
    search_fields = ("text", "session__guest_name", "sender_user__username")

    def text_snippet(self, obj):
        return obj.text[:60]
    text_snippet.short_description = "Text"


from .models import EmailOTP


@admin.register(EmailOTP)
class EmailOTPAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "otp_code", "purpose", "created_at", "expires_at", "is_used", "attempts")
    list_filter = ("purpose", "is_used", "created_at")
    search_fields = ("email", "otp_code", "user__username")
    readonly_fields = ("created_at", "expires_at", "otp_code")


