from django.conf import settings
from django.db import models


class InteractionEvent(models.Model):
    VIEW = "view"
    CLICK = "click"
    ADD_TO_CART = "add_to_cart"
    PURCHASE = "purchase"
    SEARCH = "search"
    WATCHLIST = "watchlist"

    EVENT_TYPES = [
        (VIEW, "View"),
        (CLICK, "Click"),
        (ADD_TO_CART, "Add to cart"),
        (PURCHASE, "Purchase"),
        (SEARCH, "Search"),
        (WATCHLIST, "Watchlist"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interaction_events",
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    item = models.ForeignKey(
        "business.Item",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interaction_events",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPES, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "event_type", "timestamp"]),
            models.Index(fields=["item", "event_type"]),
            models.Index(fields=["session_key", "event_type", "timestamp"]),
        ]

    def __str__(self):
        who = self.user_id or self.session_key or "?"
        return f"{self.event_type} u={who} item={self.item_id}"


class UserFeature(models.Model):
    """Lite feature-store row for a logged-in user or anonymous session."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recommend_features",
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    category_affinity = models.JSONField(default=dict, blank=True)
    recent_item_ids = models.JSONField(default=list, blank=True)
    purchase_count = models.PositiveIntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    cart_count = models.PositiveIntegerField(default=0)
    last_active = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                condition=~models.Q(session_key=""),
                name="uniq_userfeature_session",
            ),
        ]

    def __str__(self):
        if self.user_id:
            return f"UserFeature(user={self.user_id})"
        return f"UserFeature(session={self.session_key})"


class ItemFeature(models.Model):
    item = models.OneToOneField(
        "business.Item",
        on_delete=models.CASCADE,
        related_name="recommend_features",
    )
    category_id = models.IntegerField(null=True, blank=True, db_index=True)
    view_count = models.PositiveIntegerField(default=0)
    click_count = models.PositiveIntegerField(default=0)
    cart_count = models.PositiveIntegerField(default=0)
    purchase_count = models.PositiveIntegerField(default=0)
    popularity_score = models.FloatField(default=0.0, db_index=True)
    price_band = models.PositiveSmallIntegerField(default=0)
    recency_score = models.FloatField(default=0.0)
    avg_rating = models.FloatField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["-popularity_score"]),
        ]

    def __str__(self):
        return f"ItemFeature(item={self.item_id}, pop={self.popularity_score:.2f})"


class ItemSimilarity(models.Model):
    """Precomputed item–item neighbors (co-view / co-purchase)."""

    item = models.ForeignKey(
        "business.Item",
        on_delete=models.CASCADE,
        related_name="similar_to",
    )
    similar_item = models.ForeignKey(
        "business.Item",
        on_delete=models.CASCADE,
        related_name="similar_from",
    )
    score = models.FloatField(default=0.0)
    source = models.CharField(max_length=32, default="co_occurrence")

    class Meta:
        unique_together = ("item", "similar_item")
        indexes = [
            models.Index(fields=["item", "-score"]),
        ]

    def __str__(self):
        return f"{self.item_id}→{self.similar_item_id} ({self.score:.3f})"
