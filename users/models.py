from django.db import models
from django.contrib.auth.models import User

# Create your models here.


class PasswordResetRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Reset request for {self.user.username}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(
        default="profile_pictures/default_profile.jpg", upload_to="profile_pictures"
    )
    major = models.CharField(
        max_length=100, blank=True, help_text="e.g., Computer Science"
    )
    graduation_year = models.IntegerField(null=True, blank=True, help_text="e.g., 2026")
    is_email_verified = models.BooleanField(
        default=False,
        help_text="Indicates if the user has verified their university email.",
    )
    phone_number = models.CharField(
        max_length=20,
        blank=False,
        default="",
        help_text="Required — buyers contact you here (WhatsApp / call).",
    )
    linkedin_url = models.URLField(
        blank=True, help_text="Link to your LinkedIn profile."
    )
    instagram_handle = models.CharField(
        max_length=100, blank=True, help_text="Your Instagram username (without @)."
    )
    watchlist = models.ManyToManyField(
        "business.Item", blank=True, related_name="watched_by"
    )
    storage_quota_mb = models.PositiveIntegerField(
        default=100,
        verbose_name="Storage Quota (MB)",
        help_text="Allocated storage limit in megabytes (Free tier: 100MB, Premium: 1000MB+).",
    )
    storage_plan = models.CharField(
        max_length=20,
        default="free",
        choices=[
            ("free", "Free Tier (100 MB)"),
            ("pro", "Pro Seller (1 GB)"),
            ("business", "Campus Business (5 GB)"),
            ("custom", "Custom Enterprise"),
        ],
        verbose_name="Storage Plan Tier",
    )

    def get_storage_usage(self):
        from business.analytics import get_user_storage_breakdown
        return get_user_storage_breakdown(self.user, quota_mb=self.storage_quota_mb, plan_name=self.get_storage_plan_display())

    def has_storage_space(self, additional_bytes=0):
        usage = self.get_storage_usage()
        quota_bytes = self.storage_quota_mb * 1024 * 1024
        return (usage["total_bytes"] + additional_bytes) <= quota_bytes

    def __str__(self):
        return f"{self.user.username} Profile"


class EmailOTP(models.Model):
    PURPOSE_CHOICES = [
        ("registration", "Registration"),
        ("password_reset", "Password Reset"),
    ]

    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="email_otps",
    )
    email = models.EmailField(db_index=True)
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(
        max_length=20, choices=PURPOSE_CHOICES, default="registration", db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OTP {self.otp_code} for {self.email} ({self.purpose})"

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at

    @classmethod
    def create_otp(cls, email, purpose="registration", user=None, validity_minutes=10):
        import secrets
        from datetime import timedelta
        from django.utils import timezone

        clean_email = email.strip().lower()
        # Invalidate any previous active OTPs for this email and purpose
        cls.objects.filter(email__iexact=clean_email, purpose=purpose, is_used=False).update(is_used=True)

        code = f"{secrets.randbelow(900000) + 100000}"
        expires_at = timezone.now() + timedelta(minutes=validity_minutes)

        return cls.objects.create(
            user=user,
            email=clean_email,
            otp_code=code,
            purpose=purpose,
            expires_at=expires_at,
        )

    def verify(self, input_code):
        if self.is_used:
            return False, "Nambari hii ya OTP tayari imetumika. Tafadhali omba mpya."
        if self.is_expired:
            return False, "Nambari hii ya OTP imepitwa na wakati (expired). Tafadhali omba mpya."
        if self.attempts >= 5:
            return False, "Majaribio yamezidi kiwango. Tafadhali omba nambari mpya ya OTP."

        if str(self.otp_code).strip() != str(input_code).strip():
            self.attempts += 1
            self.save(update_fields=["attempts"])
            return False, "Nambari ya OTP si sahihi. Tafadhali kagua tena."

        self.is_used = True
        self.save(update_fields=["is_used"])
        return True, "Uthibitisho umefaulu."


class SupportSession(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]

    session_key = models.CharField(max_length=100, unique=True, db_index=True)
    user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_sessions",
    )
    guest_name = models.CharField(max_length=100, default="Guest")
    guest_email = models.EmailField(blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="open", db_index=True
    )
    assigned_admin = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_support_sessions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        name = self.user.username if self.user else self.guest_name
        return f"Support #{self.id} ({name}) - {self.get_status_display()}"

    @property
    def display_name(self):
        if self.user:
            return self.user.get_full_name() or self.user.username
        return self.guest_name or f"Guest #{self.id}"

    @property
    def unread_count_for_admin(self):
        return self.messages.filter(sender_type="guest", is_read=False).count()

    @property
    def unread_count_for_guest(self):
        return self.messages.filter(sender_type="admin", is_read=False).count()

    @property
    def latest_message(self):
        return self.messages.order_by("-timestamp").first()


class SupportMessage(models.Model):
    SENDER_CHOICES = [
        ("guest", "Guest / User"),
        ("admin", "Admin / Support"),
    ]

    session = models.ForeignKey(
        SupportSession, on_delete=models.CASCADE, related_name="messages"
    )
    sender_type = models.CharField(
        max_length=10, choices=SENDER_CHOICES, default="guest"
    )
    sender_user = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="support_messages_sent",
    )
    text = models.TextField()
    image = models.ImageField(
        upload_to="support_screenshots/", blank=True, null=True
    )
    page_url = models.CharField(max_length=500, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        sender = self.sender_user.username if self.sender_user else self.sender_type
        return f"[{sender}] {self.text[:30]}"

