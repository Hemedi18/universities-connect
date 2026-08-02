from django.contrib import admin
from .models import PasswordResetRequest

# Register your models here.


@admin.register(PasswordResetRequest)
class PasswordResetRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "created_at", "is_resolved")
    list_filter = ("is_resolved", "created_at")
    actions = ["mark_as_resolved"]

    def mark_as_resolved(self, request, queryset):
        queryset.update(is_resolved=True)
