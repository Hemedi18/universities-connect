from django.contrib import admin
from .models import SystemErrorLog, AdminEmailTemplate, SentEmailLog


@admin.register(SystemErrorLog)
class SystemErrorLogAdmin(admin.ModelAdmin):
    list_display = ("level", "message_short", "endpoint", "user", "ip_address", "is_resolved", "created_at")
    list_filter = ("level", "is_resolved", "created_at")
    search_fields = ("message", "endpoint", "ip_address", "traceback")
    readonly_fields = ("created_at",)

    def message_short(self, obj):
        return obj.message[:80]
    message_short.short_description = "Message"


@admin.register(AdminEmailTemplate)
class AdminEmailTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "subject", "created_at", "updated_at")
    list_filter = ("category", "created_at")
    search_fields = ("name", "subject", "html_body")


@admin.register(SentEmailLog)
class SentEmailLogAdmin(admin.ModelAdmin):
    list_display = ("recipient_email", "sender_email", "subject", "status", "sent_by", "sent_at")
    list_filter = ("status", "sender_email", "sent_at")
    search_fields = ("recipient_email", "subject", "body")
    readonly_fields = ("sent_at",)
