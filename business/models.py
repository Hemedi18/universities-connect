from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

# Create your models here.

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE)
    code = models.CharField(max_length=20, blank=True, null=True, verbose_name="Category ID")
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
            existing_codes = Category.objects.filter(code__startswith='CAT-').values_list('code', flat=True)
            max_val = 0
            for c in existing_codes:
                try:
                    val = int(c.split('-')[1])
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
    categories = models.ManyToManyField(Category, related_name='attributes', blank=True)
    options = models.TextField(blank=True, null=True, help_text="Comma-separated options for dropdowns")
    
    def __str__(self):
        return self.name

class Company(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_profile')
    name = models.CharField(max_length=255)
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    followers = models.ManyToManyField(User, related_name='following_companies', blank=True)
    is_verified = models.BooleanField(default=False)
    address = models.CharField(max_length=255, blank=True, help_text="Physical location of the company")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Companies"

class Item(models.Model):
    # --- Global Requirements (Mandatory for ALL Products) ---
    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    
    # Product ID / SKU
    sku = models.CharField(max_length=100, unique=True, blank=True, null=True, verbose_name="Product ID / SKU")
    
    # Product Title
    title = models.CharField(max_length=255, verbose_name="Product Title")
    
    # Category (Link to Categories Table)
    category = models.CharField(max_length=50, default='others', blank=True) # Kept for legacy data
    category_obj = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='items', verbose_name="Category")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    
    # Base Price & Compare Price
    price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Base Price")
    compare_at_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, verbose_name="Compare at Price")
    
    # Stock Quantity
    stock_quantity = models.IntegerField(default=1, verbose_name="Stock Quantity")
    minimum_order_quantity = models.IntegerField(default=1, verbose_name="Minimum Order Quantity")
    
    # Product Description
    description = models.TextField(verbose_name="Product Description")
    
    # Product Images
    image = models.ImageField(upload_to='item_images/', verbose_name="Main Image")
    image2 = models.ImageField(upload_to='item_images/', blank=True, null=True, verbose_name="Image 2")
    image3 = models.ImageField(upload_to='item_images/', blank=True, null=True, verbose_name="Image 3")
    
    # Shipping Weight & Dimensions
    shipping_weight = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="kg")
    shipping_dimensions = models.CharField(max_length=100, blank=True, null=True, help_text="L x W x H")
    
    # Tax Class
    tax_class = models.CharField(max_length=50, default="Standard", blank=True)

    # --- Legacy / App Specific Fields (Kept for compatibility) ---
    CONTACT_METHOD_CHOICES = [
        ('chat', 'In-app Chat'),
        ('email', 'University Email'),
        ('phone', 'Phone Number'),
    ]
    
    condition = models.CharField(max_length=50, choices=[('new', 'New'), ('used', 'Used')], default='used', blank=True)
    campus_location = models.CharField(max_length=255, blank=True, verbose_name="Campus/Location", help_text="Specific campus or dorm")
    contact_method = models.CharField(max_length=50, choices=CONTACT_METHOD_CHOICES, verbose_name="Contact Method")
    contact_email = models.EmailField(blank=True, verbose_name="Contact Email", help_text="Required if Contact Method is Email")
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Contact Phone", help_text="Required if Contact Method is Phone")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, default='active')
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases')
    is_pinned = models.BooleanField(default=False, verbose_name="Pinned to Top")
    views = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

class ProductAttributeValue(models.Model):
    product = models.ForeignKey(Item, related_name='attribute_values', on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=255)
    
    def __str__(self):
        return f"{self.product.title} - {self.attribute.name}: {self.value}"

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}"

class Review(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(default=5)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class Comment(models.Model):
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user} on {self.item}"

class Report(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='reports')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Report: {self.company.name}"

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
            notifications_to_create.append(Notification(
                recipient=user,
                message=f"New from {instance.company.name}: {instance.title}",
                link=f"/item/{instance.id}/"
            ))
        Notification.objects.bulk_create(notifications_to_create)

        recipient_list = [user.email for user in followers if user.email]
        
        if recipient_list:
            subject = f"New Product from {instance.company.name}: {instance.title}"
            # In production, use your actual domain or Django's Site framework
            item_url = f"http://127.0.0.1:8000/item/{instance.id}/"
            
            message = (
                f"Hello,\n\n"
                f"{instance.company.name} has just posted a new product: {instance.title}.\n\n"
                f"Price: {instance.price}\n\n"
                f"View it here: {item_url}\n\n"
                f"Best regards,\nU-Connect Team"
            )
            
            send_mail(
                subject,
                message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@u-connect.com'),
                recipient_list,
                fail_silently=True
            )
