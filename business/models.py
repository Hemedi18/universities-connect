from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

# Create your models here.


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    code = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="Category ID"
    )
    target_market = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify

            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if not self.code:
            # Auto-generate code (CAT-XX) if not provided
            existing_codes = Category.objects.filter(
                code__startswith="CAT-"
            ).values_list("code", flat=True)
            max_val = 0
            for c in existing_codes:
                try:
                    val = int(c.split("-")[1])
                    if val > max_val:
                        max_val = val
                except (IndexError, ValueError):
                    pass
            self.code = f"CAT-{max_val + 1:02d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Attribute(models.Model):
    name = models.CharField(max_length=100)
    categories = models.ManyToManyField(Category, related_name="attributes", blank=True)
    options = models.TextField(
        blank=True, null=True, help_text="Comma-separated options for dropdowns"
    )

    def __str__(self):
        return self.name


class Item(models.Model):
    # --- Global Requirements (Mandatory for ALL Products) ---
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    sku = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Product ID / SKU",
    )
    title = models.CharField(max_length=255, verbose_name="Product Title")
    category = models.CharField(
        max_length=50, default="others", blank=True
    )  # Kept for legacy data
    category_obj = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="items",
        verbose_name="Category",
    )
    company = models.ForeignKey(
        "company.Company",
        on_delete=models.CASCADE,
        related_name="items",
        null=True,
        blank=True,
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Price",
        help_text="Selling price.",
    )
    compare_at_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name="Compare at",
        help_text="Optional higher reference price (shown struck through).",
    )
    stock_quantity = models.IntegerField(default=1, verbose_name="Stock Quantity")
    minimum_order_quantity = models.IntegerField(
        default=1, verbose_name="Minimum Order Quantity"
    )
    description = models.TextField(verbose_name="Product Description")
    image = models.ImageField(
        upload_to="item_images/",
        verbose_name="Main Image",
        blank=True,
        null=True,
    )
    image2 = models.ImageField(
        upload_to="item_images/", blank=True, null=True, verbose_name="Image 2"
    )
    image3 = models.ImageField(
        upload_to="item_images/", blank=True, null=True, verbose_name="Image 3"
    )
    video = models.FileField(
        upload_to="item_videos/",
        blank=True,
        null=True,
        verbose_name="Product video",
        help_text="Optional short clip (max 30 seconds). MP4 / WebM / MOV.",
    )
    shipping_weight = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, help_text="kg"
    )
    shipping_dimensions = models.CharField(
        max_length=100, blank=True, null=True, help_text="L x W x H"
    )
    tax_class = models.CharField(max_length=50, default="Standard", blank=True)

    # --- Legacy / App Specific Fields (Kept for compatibility) ---
    CONTACT_METHOD_CHOICES = [
        ("chat", "In-app Chat"),
        ("email", "University Email"),
        ("phone", "Phone Number"),
    ]

    condition = models.CharField(
        max_length=50,
        choices=[("new", "New"), ("used", "Used")],
        default="used",
        blank=True,
    )
    campus_location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Campus/Location",
        help_text="Legacy / combined location string",
    )
    general_location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="General Location / Area",
        help_text="e.g. Chukwani, Zanzibar or Mwenge, Dar es Salaam",
    )
    specific_location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Specific Meetup Spot",
        help_text="e.g. SUMAIT University, Block B Entrance",
    )
    location_latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Location Latitude",
    )
    location_longitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Location Longitude",
    )
    contact_method = models.CharField(
        max_length=50, choices=CONTACT_METHOD_CHOICES, verbose_name="Contact Method"
    )
    contact_email = models.EmailField(
        blank=True,
        verbose_name="Contact Email",
        help_text="Required if Contact Method is Email",
    )
    contact_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Contact Phone",
        help_text="Required if Contact Method is Phone",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default="active")
    buyer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="purchases"
    )
    is_pinned = models.BooleanField(default=False, verbose_name="Pinned to Top")
    views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

    def get_general_location(self):
        if self.general_location:
            return self.general_location
        if self.campus_location:
            return self.campus_location
        return ""

    def get_full_location(self):
        parts = []
        if self.specific_location:
            parts.append(self.specific_location)
        if self.general_location:
            parts.append(self.general_location)
        if parts:
            return ", ".join(parts)
        return self.campus_location or ""

    def get_google_maps_url(self):
        import urllib.parse
        if self.location_latitude is not None and self.location_longitude is not None:
            return f"https://www.google.com/maps/search/?api=1&query={self.location_latitude},{self.location_longitude}"
        loc = self.get_full_location()
        if loc:
            return f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(loc)}"
        return ""

    def get_google_maps_directions_url(self, origin=None):
        import urllib.parse
        dest = f"{self.location_latitude},{self.location_longitude}" if (self.location_latitude is not None and self.location_longitude is not None) else self.get_full_location()
        if not dest:
            return ""
        base = f"https://www.google.com/maps/dir/?api=1&destination={urllib.parse.quote(str(dest))}"
        if origin:
            base += f"&origin={urllib.parse.quote(str(origin))}"
        return base

    def save(self, *args, **kwargs):
        # Auto-synchronize legacy campus_location with general & specific
        if self.general_location or self.specific_location:
            self.campus_location = self.get_full_location()
        elif self.campus_location and not self.general_location:
            self.general_location = self.campus_location
        super().save(*args, **kwargs)

    def gallery_media(self):
        """Prefer ItemMedia rows; fall back to legacy image/image2/image3/video."""
        rows = list(self.media.all())
        if rows:
            return rows
        legacy = []
        order = 0
        for field, mtype in (
            ("image", "image"),
            ("image2", "image"),
            ("image3", "image"),
            ("video", "video"),
        ):
            f = getattr(self, field, None)
            if f:
                legacy.append(
                    type(
                        "LegacyMedia",
                        (),
                        {
                            "id": None,
                            "file": f,
                            "media_type": mtype,
                            "sort_order": order,
                            "is_legacy": True,
                        },
                    )()
                )
                order += 1
        return legacy

    def sync_legacy_media_fields(self):
        """Copy first images/video from ItemMedia into legacy columns for cards."""
        medias = list(self.media.all())
        images = [m for m in medias if m.media_type == "image"]
        videos = [m for m in medias if m.media_type == "video"]

        self.image = images[0].file if len(images) > 0 else None
        self.image2 = images[1].file if len(images) > 1 else None
        self.image3 = images[2].file if len(images) > 2 else None
        self.video = videos[0].file if videos else None
        self.save(update_fields=["image", "image2", "image3", "video"])


class ItemMedia(models.Model):
    MEDIA_IMAGE = "image"
    MEDIA_VIDEO = "video"
    MEDIA_TYPES = (
        (MEDIA_IMAGE, "Image"),
        (MEDIA_VIDEO, "Video"),
    )

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="media")
    file = models.FileField(upload_to="item_media/")
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default=MEDIA_IMAGE)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]

    def __str__(self):
        return f"{self.item_id} · {self.media_type} · {self.sort_order}"

    @property
    def is_video(self):
        return self.media_type == self.MEDIA_VIDEO

    @property
    def is_image(self):
        return self.media_type == self.MEDIA_IMAGE


class ProductAttributeValue(models.Model):
    product = models.ForeignKey(
        Item, related_name="attribute_values", on_delete=models.CASCADE
    )
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.product.title} - {self.attribute.name}: {self.value}"


class Notification(models.Model):
    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification for {self.recipient.username}"


@receiver(post_save, sender=Item)
def send_new_item_notification(sender, instance, created, **kwargs):
    """
    Signal to send email notification to company followers when a new item is posted.
    """
    if created and instance.company:
        followers = instance.company.followers.all()

        # Create in-app notifications
        notifications_to_create = []
        for user in followers:
            notifications_to_create.append(
                Notification(
                    recipient=user,
                    message=f"New from {instance.company.name}: {instance.title}",
                    link=f"/item/{instance.id}/",
                )
            )
        Notification.objects.bulk_create(notifications_to_create)

        recipient_list = [user.email for user in followers if user.email]

        if recipient_list:
            subject = f"Bidhaa Mpya: {instance.company.name} - {instance.title}"
            base_url = getattr(settings, "SITE_URL", "https://uconnect.edusphere.co.tz")
            item_url = f"{base_url}/item/{instance.id}/"

            plain_message = (
                f"Habari,\n\n"
                f"{instance.company.name} amechapisha bidhaa mpya: {instance.title}.\n\n"
                f"Bei: TZS {instance.price}\n\n"
                f"Tazama bidhaa hapa: {item_url}\n\n"
                f"U-Connect Marketplace\nhttps://uconnect.edusphere.co.tz"
            )

            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "U-Connect <updates@uconnect.edusphere.co.tz>")

            try:
                html_content = render_to_string("emails/new_product_email.html", {
                    "subject": subject,
                    "item": instance,
                    "item_url": item_url,
                    "site_url": base_url,
                })
            except Exception:
                html_content = None

            for email in recipient_list:
                try:
                    msg = EmailMultiAlternatives(
                        subject=subject,
                        body=plain_message,
                        from_email=from_email,
                        to=[email],
                    )
                    if html_content:
                        msg.attach_alternative(html_content, "text/html")
                    msg.send(fail_silently=True)
                except Exception:
                    pass


class Comment(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user} on {self.item}"


class SellerMeetupLocation(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_meetup_locations"
    )
    general_location = models.CharField(
        max_length=255,
        verbose_name="General Location / Area",
        help_text="e.g. Chukwani, Zanzibar",
    )
    specific_location = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Specific Meetup Spot",
        help_text="e.g. SUMAIT University, Block B",
    )
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_default = models.BooleanField(
        default=False,
        verbose_name="Default Location",
        help_text="Automatically selected for new product listings",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name = "Seller Meetup Location"
        verbose_name_plural = "Seller Meetup Locations"

    def __str__(self):
        if self.specific_location:
            return f"{self.general_location} ({self.specific_location})"
        return self.general_location

    def save(self, *args, **kwargs):
        if self.is_default:
            SellerMeetupLocation.objects.filter(
                user=self.user, is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


@receiver(post_save, sender="company.Company")
def migrate_personal_items_to_company(sender, instance, created, **kwargs):
    """
    When a Company is created, move the user's existing personal items to the company.
    """
    if created:
        Item.objects.filter(seller=instance.user, company__isnull=True).update(
            company=instance
        )
