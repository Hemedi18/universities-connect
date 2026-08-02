from django import template

register = template.Library()


@register.filter(name="tsh")
def tsh(value):
    """Format as Tanzanian shillings, e.g. Tsh 2,000."""
    if value is None or value == "":
        return "Tsh 0"
    try:
        amount = int(round(float(value)))
    except (TypeError, ValueError):
        return f"Tsh {value}"
    return f"Tsh {amount:,}"
