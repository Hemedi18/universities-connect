from decimal import Decimal

from django import template

register = template.Library()


@register.inclusion_tag("tancoin/price_display.html", takes_context=True)
def tancoin_price_display(context, price, compare_at=None, variant="default"):
    """
    variant: 'default' | 'large' | 'compact' (single line, no fiat subline)
    """
    ex = context.get("tancoin_exchange")
    fiat_amount = None
    fiat_code = None
    compare_fiat = None
    if ex and price is not None:
        p = Decimal(str(price))
        fiat_amount = (p * ex.fiat_per_one_tan).quantize(Decimal("0.01"))
        fiat_code = ex.fiat_currency_code
        if compare_at:
            compare_fiat = (Decimal(str(compare_at)) * ex.fiat_per_one_tan).quantize(
                Decimal("0.01")
            )
    return {
        "price": price,
        "compare_at": compare_at,
        "fiat_amount": fiat_amount,
        "fiat_code": fiat_code,
        "compare_fiat": compare_fiat,
        "variant": variant,
    }
