from django.contrib import admin

from .models import Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "title",
        "sku",
        "unit_price_tan",
        "quantity",
        "line_total_tan",
        "seller",
        "company",
        "item",
    )


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "order_number",
        "buyer",
        "status",
        "payment_status",
        "payment_method",
        "total_tan",
        "created_at",
    )
    list_filter = ("status", "payment_status", "payment_method", "fulfillment_method")
    search_fields = (
        "order_number",
        "buyer__username",
        "full_name",
        "phone",
        "payment_reference",
    )
    readonly_fields = ("order_number", "created_at", "updated_at", "paid_at")
    inlines = [OrderItemInline, PaymentInline]
    date_hierarchy = "created_at"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "order",
        "seller",
        "quantity",
        "unit_price_tan",
        "line_total_tan",
        "fulfillment_status",
    )
    list_filter = ("fulfillment_status",)
    search_fields = ("title", "sku", "order__order_number", "seller__username")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "amount_tan", "status", "reference", "created_at")
    list_filter = ("status", "method")
    search_fields = ("order__order_number", "reference")
