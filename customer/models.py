import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PROCESSING = "processing"
    STATUS_SHIPPED = "shipped"
    STATUS_READY = "ready_for_pickup"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_SHIPPED, "Shipped"),
        (STATUS_READY, "Ready for Pickup"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    FULFILLMENT_PICKUP = "campus_pickup"
    FULFILLMENT_DELIVERY = "delivery"
    FULFILLMENT_CHOICES = [
        (FULFILLMENT_PICKUP, "Campus Pickup / Meetup"),
        (FULFILLMENT_DELIVERY, "Delivery"),
    ]

    PAY_MEETUP = "campus_meetup"
    PAY_COD = "cash_on_delivery"
    PAY_MOMO = "mobile_money"
    PAY_BANK = "bank_transfer"
    PAYMENT_METHOD_CHOICES = [
        (PAY_MEETUP, "Pay at Meetup"),
        (PAY_COD, "Cash on Delivery"),
        (PAY_MOMO, "Mobile Money"),
        (PAY_BANK, "Bank Transfer"),
    ]

    PAY_PENDING = "pending"
    PAY_AWAITING = "awaiting_confirmation"
    PAY_PAID = "paid"
    PAY_FAILED = "failed"
    PAY_REFUNDED = "refunded"
    PAYMENT_STATUS_CHOICES = [
        (PAY_PENDING, "Pending"),
        (PAY_AWAITING, "Awaiting Confirmation"),
        (PAY_PAID, "Paid"),
        (PAY_FAILED, "Failed"),
        (PAY_REFUNDED, "Refunded"),
    ]

    order_number = models.CharField(max_length=32, unique=True, db_index=True)
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )
    payment_method = models.CharField(max_length=32, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(
        max_length=32,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAY_PENDING,
        db_index=True,
    )
    fulfillment_method = models.CharField(
        max_length=32, choices=FULFILLMENT_CHOICES, default=FULFILLMENT_PICKUP
    )

    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    campus_location = models.CharField(max_length=255, blank=True)
    address_line = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    subtotal_tan = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    shipping_fee_tan = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    tax_tan = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_tan = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    fiat_currency_code = models.CharField(max_length=10, blank=True, default="TZS")
    fiat_rate_snapshot = models.DecimalField(
        max_digits=24, decimal_places=6, null=True, blank=True
    )
    total_fiat_estimate = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )

    payment_reference = models.CharField(max_length=100, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    stock_restored = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number

    @staticmethod
    def generate_order_number():
        stamp = timezone.now().strftime("%Y%m%d")
        return f"UC-{stamp}-{uuid.uuid4().hex[:8].upper()}"

    def mark_paid(self, reference="", user=None):
        self.payment_status = self.PAY_PAID
        self.paid_at = timezone.now()
        if reference:
            self.payment_reference = reference
        if self.status == self.STATUS_PENDING:
            self.status = self.STATUS_CONFIRMED
        self.save(
            update_fields=[
                "payment_status",
                "paid_at",
                "payment_reference",
                "status",
                "updated_at",
            ]
        )
        payment, _ = Payment.objects.get_or_create(
            order=self,
            defaults={
                "method": self.payment_method,
                "amount_tan": self.total_tan,
                "status": Payment.STATUS_CONFIRMED,
                "reference": reference or self.payment_reference,
                "recorded_by": user,
                "confirmed_at": timezone.now(),
            },
        )
        if payment.status != Payment.STATUS_CONFIRMED:
            payment.status = Payment.STATUS_CONFIRMED
            payment.reference = reference or payment.reference or self.payment_reference
            payment.recorded_by = user or payment.recorded_by
            payment.confirmed_at = timezone.now()
            payment.save()

    def can_cancel(self):
        return self.status not in (self.STATUS_COMPLETED, self.STATUS_CANCELLED, self.STATUS_SHIPPED)


class OrderItem(models.Model):
    FULFILLMENT_PENDING = "pending"
    FULFILLMENT_CONFIRMED = "confirmed"
    FULFILLMENT_SHIPPED = "shipped"
    FULFILLMENT_READY = "ready_for_pickup"
    FULFILLMENT_COMPLETED = "completed"
    FULFILLMENT_CANCELLED = "cancelled"
    FULFILLMENT_CHOICES = [
        (FULFILLMENT_PENDING, "Pending"),
        (FULFILLMENT_CONFIRMED, "Confirmed"),
        (FULFILLMENT_SHIPPED, "Shipped"),
        (FULFILLMENT_READY, "Ready for Pickup"),
        (FULFILLMENT_COMPLETED, "Completed"),
        (FULFILLMENT_CANCELLED, "Cancelled"),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item = models.ForeignKey(
        "business.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sold_order_items",
    )
    company = models.ForeignKey(
        "company.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items",
    )
    title = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True)
    unit_price_tan = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    line_total_tan = models.DecimalField(max_digits=14, decimal_places=2)
    fulfillment_status = models.CharField(
        max_length=32,
        choices=FULFILLMENT_CHOICES,
        default=FULFILLMENT_PENDING,
    )

    def __str__(self):
        return f"{self.title} x{self.quantity}"

    def save(self, *args, **kwargs):
        self.line_total_tan = (
            Decimal(self.unit_price_tan) * Decimal(self.quantity)
        ).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class Payment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_CONFIRMED, "Confirmed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name="payment"
    )
    method = models.CharField(max_length=32, choices=Order.PAYMENT_METHOD_CHOICES)
    amount_tan = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payment for {self.order.order_number}"
