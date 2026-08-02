from django.contrib import admin

from .models import Conversation, DealRating, ItemDeal, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    raw_id_fields = ("sender", "item")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "updated_at")
    filter_horizontal = ("participants",)
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "item", "timestamp", "is_read")
    list_filter = ("is_read",)
    raw_id_fields = ("conversation", "sender", "item")


@admin.register(ItemDeal)
class ItemDealAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item",
        "buyer",
        "seller",
        "status",
        "quantity",
        "rating_requested",
        "updated_at",
    )
    list_filter = ("status", "rating_requested")
    raw_id_fields = ("conversation", "item", "buyer", "seller")


@admin.register(DealRating)
class DealRatingAdmin(admin.ModelAdmin):
    list_display = ("id", "deal", "item", "buyer", "rating", "created_at")
    raw_id_fields = ("deal", "item", "buyer", "seller")
