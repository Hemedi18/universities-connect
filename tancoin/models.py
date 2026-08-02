from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.core.cache import cache
from django.db import models


class ExchangeRate(models.Model):
    """
    Reference rate: how much one unit of fiat is worth relative to TAN,
    stored as fiat_per_one_tan (1 TAN = X units of fiat, e.g. TZS).
    """

    fiat_currency_code = models.CharField(
        max_length=10,
        default="TZS",
        help_text="ISO-style code shown next to fiat estimates (e.g. TZS, USD).",
    )
    fiat_per_one_tan = models.DecimalField(
        max_digits=24,
        decimal_places=6,
        help_text="Example: if 1 TAN = 500 TZS, enter 500.",
    )
    notes = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Exchange rate"
        verbose_name_plural = "Exchange rates"

    def __str__(self):
        return f"1 TAN = {self.fiat_per_one_tan} {self.fiat_currency_code}"

    @classmethod
    def get_active(cls):
        """Latest rate row; cached briefly to avoid extra queries on list pages."""
        key = "tancoin:active_exchange_rate_id"
        pk = cache.get(key)
        if pk is not None:
            row = cls.objects.filter(pk=pk).first()
            if row:
                return row
        row = cls.objects.order_by("-updated_at", "-id").first()
        if row:
            cache.set(key, row.pk, timeout=60)
        return row

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete("tancoin:active_exchange_rate_id")

    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        cache.delete("tancoin:active_exchange_rate_id")

    def tan_to_fiat(self, amount_tan) -> Optional[Decimal]:
        if amount_tan is None:
            return None
        amt = Decimal(str(amount_tan)) * self.fiat_per_one_tan
        return amt.quantize(Decimal("0.01"))
