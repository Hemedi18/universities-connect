from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from .models import Category, Attribute, Item, ProductAttributeValue

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'parent', 'slug')
    search_fields = ('name', 'code')
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ('parent',)

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_options_preview')
    search_fields = ('name',)
    filter_horizontal = ('categories',)

    def get_options_preview(self, obj):
        if obj.options:
            return (obj.options[:75] + '...') if len(obj.options) > 75 else obj.options
        return "-"
    get_options_preview.short_description = "Options"

class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 1

@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'price', 'category_obj', 'seller', 'status', 'created_at', 'chat_with_seller')
    list_display_links = ('id', 'title')
    list_filter = ('status', 'category_obj', 'created_at')
    search_fields = ('title', 'description', 'sku', 'seller__username', 'seller__email')
    inlines = [ProductAttributeValueInline]
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)

    def chat_with_seller(self, obj):
        if obj.seller:
            url = reverse('chat:start_chat', args=[obj.seller.id])
            return format_html('<a class="button" href="{}" target="_blank" style="background-color: #4f46e5; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none;">Chat</a>', url)
        return "-"
    chat_with_seller.short_description = 'Contact Seller'

@admin.register(ProductAttributeValue)
class ProductAttributeValueAdmin(admin.ModelAdmin):
    list_display = ('product', 'attribute', 'value')
    list_filter = ('attribute',)
    search_fields = ('product__title', 'attribute__name', 'value')

# Unregister existing User admin to extend it
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'start_chat_link')
    
    def start_chat_link(self, obj):
        url = reverse('chat:start_chat', args=[obj.id])
        return format_html('<a class="button" href="{}" target="_blank" style="background-color: #4f46e5; color: white; padding: 4px 10px; border-radius: 4px; text-decoration: none;">Chat</a>', url)
    start_chat_link.short_description = 'Chat'