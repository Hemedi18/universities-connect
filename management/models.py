from django.db import models
from django.contrib.auth.models import User


class SystemErrorLog(models.Model):
    """
    Logs website exceptions, authentication security failures, and diagnostic events
    so administrators can troubleshoot issues directly in the Command Center.
    """
    LEVEL_CHOICES = (
        ("ERROR", "Error / Exception"),
        ("WARNING", "Warning"),
        ("SECURITY", "Security Alert"),
        ("INFO", "Information"),
    )

    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="ERROR")
    message = models.TextField()
    endpoint = models.CharField(max_length=255, blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="system_errors")
    traceback = models.TextField(blank=True, null=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="resolved_system_errors")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "System Error Log"
        verbose_name_plural = "System Error Logs"

    def __str__(self):
        return f"[{self.level}] {self.message[:60]} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class AdminEmailTemplate(models.Model):
    """
    Reusable email templates for customer communication, dispute handling,
    marketing broadcasts, and system notices.
    """
    CATEGORY_CHOICES = (
        ("support", "Support & Inquiries"),
        ("security", "Security & Accounts"),
        ("marketing", "Marketing & Promotions"),
        ("notification", "System Updates"),
    )

    name = models.CharField(max_length=150, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default="support")
    subject = models.CharField(max_length=255)
    html_body = models.TextField(help_text="HTML formatted body with support for {{ username }}, {{ site_url }}, etc.")
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class SentEmailLog(models.Model):
    """
    Audit log of all outgoing customer emails dispatched directly from the Command Center.
    """
    STATUS_CHOICES = (
        ("sent", "Sent Successfully"),
        ("failed", "Failed"),
    )

    sender_email = models.EmailField()
    recipient_email = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField(blank=True, null=True)
    template = models.ForeignKey(AdminEmailTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="sent")
    error_message = models.TextField(blank=True, null=True)
    sent_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"To: {self.recipient_email} | {self.subject} ({self.status})"
