from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class Item(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending Sale'),
        ('sold', 'Sold'),
    ]

    CATEGORY_CHOICES = [
        ('books', 'Books'),
        ('electronics', 'Electronics'),
        ('furniture', 'Furniture'),
        ('clothing', 'Clothing'),
        ('others', 'Others'),
    ]

    CONDITION_CHOICES = [
        ('new', 'New'),
        ('like_new', 'Like New'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]

    CONTACT_METHOD_CHOICES = [
        ('chat', 'In-app Chat'),
        ('email', 'University Email'),
        ('phone', 'Phone Number'),
    ]

    seller = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, verbose_name="Product Title", help_text="e.g., 'Organic Chemistry 2nd Ed Textbook'")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    price = models.CharField(max_length=50, help_text="e.g., $50, Negotiable, or Free")
    condition = models.CharField(max_length=50, choices=CONDITION_CHOICES)
    description = models.TextField(verbose_name="Description", help_text="Details about wear and tear, specs, or why it's being sold")
    campus_location = models.CharField(max_length=255, blank=True, verbose_name="Campus/Location", help_text="Specific campus or dorm")
    preferred_meetup = models.CharField(max_length=255, blank=True, verbose_name="Preferred Meetup", help_text="Specific safe spots (e.g., 'The Student Union' or 'Library Lobby')")
    contact_method = models.CharField(max_length=50, choices=CONTACT_METHOD_CHOICES, verbose_name="Contact Method")
    contact_email = models.EmailField(blank=True, verbose_name="Contact Email", help_text="Required if Contact Method is Email")
    contact_phone = models.CharField(max_length=20, blank=True, verbose_name="Contact Phone", help_text="Required if Contact Method is Phone")
    image = models.ImageField(upload_to='item_images/', verbose_name="Cover Photo")
    image2 = models.ImageField(upload_to='item_images/', blank=True, null=True, verbose_name="Optional Photo 2")
    image3 = models.ImageField(upload_to='item_images/', blank=True, null=True, verbose_name="Optional Photo 3")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='purchases')

    def __str__(self):
        return self.title
