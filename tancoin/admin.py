from django.contrib import admin

from .models import ExchangeRate


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("fiat_currency_code", "fiat_per_one_tan", "updated_at", "notes")
    list_editable = ("fiat_per_one_tan",)
    ordering = ("-updated_at",)
