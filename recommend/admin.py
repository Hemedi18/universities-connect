from django.contrib import admin

from .models import InteractionEvent, ItemFeature, ItemSimilarity, UserFeature


@admin.register(InteractionEvent)
class InteractionEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "user", "session_key", "item", "timestamp")
    list_filter = ("event_type",)
    search_fields = ("session_key", "user__username", "item__title")
    readonly_fields = ("timestamp",)
    raw_id_fields = ("user", "item")


@admin.register(UserFeature)
class UserFeatureAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "session_key",
        "view_count",
        "purchase_count",
        "last_active",
        "updated_at",
    )
    search_fields = ("session_key", "user__username")
    raw_id_fields = ("user",)


@admin.register(ItemFeature)
class ItemFeatureAdmin(admin.ModelAdmin):
    list_display = (
        "item",
        "popularity_score",
        "view_count",
        "purchase_count",
        "category_id",
        "updated_at",
    )
    search_fields = ("item__title",)
    raw_id_fields = ("item",)
    ordering = ("-popularity_score",)


@admin.register(ItemSimilarity)
class ItemSimilarityAdmin(admin.ModelAdmin):
    list_display = ("item", "similar_item", "score", "source")
    search_fields = ("item__title", "similar_item__title")
    raw_id_fields = ("item", "similar_item")
    ordering = ("-score",)
