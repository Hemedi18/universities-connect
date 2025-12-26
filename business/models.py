from django.db import models
from django.contrib.auth.models import User

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
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Attribute(models.Model):
    name = models.CharField(max_length=100)
    categories = models.ManyToManyField(Category, related_name='attributes', blank=True)
    options = models.TextField(blank=True, null=True, help_text="Comma-separated options for dropdowns")
    
    def __str__(self):
        return self.name

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

    def __str__(self):
        return self.title

class ProductAttributeValue(models.Model):
    product = models.ForeignKey(Item, related_name='attribute_values', on_delete=models.CASCADE)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    value = models.CharField(max_length=255)
    
    def __str__(self):
        return f"{self.product.title} - {self.attribute.name}: {self.value}"
