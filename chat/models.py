from django.db import models
from django.contrib.auth.models import User


class Conversation(models.Model):
    participants = models.ManyToManyField(User, related_name="conversations")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversation {self.id}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        User, related_name="sent_messages", on_delete=models.CASCADE
    )
    content = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    image = models.ImageField(upload_to="chat_images/", blank=True, null=True)
    item = models.ForeignKey(
        "business.Item",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chat_messages",
    )

    class Meta:
        ordering = ["timestamp"]


class ItemDeal(models.Model):
    """Track chat-based sale confirmation between buyer and seller for an item."""

    PENDING = "pending"
    SOLD = "sold"
    NOT_SOLD = "not_sold"
    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (SOLD, "Sold"),
        (NOT_SOLD, "Not sold"),
    ]

    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="deals"
    )
    item = models.ForeignKey(
        "business.Item", on_delete=models.CASCADE, related_name="chat_deals"
    )
    buyer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="item_deals_as_buyer"
    )
    seller = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="item_deals_as_seller"
    )
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=PENDING, db_index=True
    )
    quantity = models.PositiveIntegerField(default=1)
    rating_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "item", "buyer"],
                name="uniq_deal_conversation_item_buyer",
            )
        ]

    def __str__(self):
        return f"Deal {self.id} item={self.item_id} {self.status}"


class DealRating(models.Model):
    """Buyer rating after seller marks a chat deal as sold."""

    deal = models.OneToOneField(
        ItemDeal, on_delete=models.CASCADE, related_name="rating"
    )
    item = models.ForeignKey(
        "business.Item", on_delete=models.CASCADE, related_name="deal_ratings"
    )
    buyer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="deal_ratings_given"
    )
    seller = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="deal_ratings_received"
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rating {self.rating}★ deal={self.deal_id}"
