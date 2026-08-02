"""Session cart helpers. Cart shape: {"<item_id>": <qty>, ...}"""

from decimal import Decimal

from django.shortcuts import get_object_or_404

from business.models import Item
from tancoin.models import ExchangeRate


def _normalize_cart(raw):
    """Migrate legacy list carts to dict form."""
    if raw is None:
        return {}
    if isinstance(raw, dict):
        out = {}
        for key, qty in raw.items():
            try:
                item_id = str(int(key))
                quantity = max(1, int(qty))
            except (TypeError, ValueError):
                continue
            out[item_id] = quantity
        return out
    if isinstance(raw, list):
        out = {}
        for entry in raw:
            try:
                item_id = str(int(entry))
            except (TypeError, ValueError):
                continue
            out[item_id] = out.get(item_id, 0) + 1
        return out
    return {}


def get_cart(session):
    cart = _normalize_cart(session.get("cart"))
    session["cart"] = cart
    return cart


def save_cart(session, cart):
    session["cart"] = cart
    session.modified = True


def cart_item_count(session):
    """Number of distinct products in cart (not sum of quantities)."""
    return len(get_cart(session))


def add_item(session, item_id, quantity=1):
    cart = get_cart(session)
    key = str(int(item_id))
    quantity = max(1, int(quantity))
    item = get_object_or_404(Item, pk=item_id, status="active")
    current = cart.get(key, 0)
    new_qty = min(current + quantity, max(item.stock_quantity, 0) or quantity)
    if item.stock_quantity <= 0:
        return False, "This item is out of stock."
    if new_qty < item.minimum_order_quantity and current == 0:
        new_qty = min(item.minimum_order_quantity, item.stock_quantity)
    cart[key] = new_qty
    save_cart(session, cart)
    return True, None


def update_item(session, item_id, quantity):
    cart = get_cart(session)
    key = str(int(item_id))
    item = get_object_or_404(Item, pk=item_id)
    quantity = int(quantity)
    if quantity <= 0:
        cart.pop(key, None)
        save_cart(session, cart)
        return True, None
    if quantity > item.stock_quantity:
        return False, f"Only {item.stock_quantity} in stock."
    if quantity < item.minimum_order_quantity:
        return False, f"Minimum order quantity is {item.minimum_order_quantity}."
    cart[key] = quantity
    save_cart(session, cart)
    return True, None


def remove_item(session, item_id):
    cart = get_cart(session)
    cart.pop(str(int(item_id)), None)
    save_cart(session, cart)


def clear_cart(session):
    save_cart(session, {})


def get_cart_lines(session):
    """Return list of dicts with item, quantity, line_total and cart totals."""
    cart = get_cart(session)
    if not cart:
        return [], Decimal("0"), None

    ids = [int(k) for k in cart.keys()]
    items = Item.objects.filter(id__in=ids, status="active").select_related(
        "company", "seller", "seller__profile", "category_obj"
    )
    by_id = {str(item.id): item for item in items}

    lines = []
    subtotal = Decimal("0")
    stale = False
    for key, qty in list(cart.items()):
        item = by_id.get(key)
        if not item:
            cart.pop(key, None)
            stale = True
            continue
        qty = min(qty, item.stock_quantity) if item.stock_quantity >= 0 else qty
        if qty <= 0:
            cart.pop(key, None)
            stale = True
            continue
        line_total = (Decimal(item.price) * Decimal(qty)).quantize(Decimal("0.01"))
        lines.append(
            {
                "item": item,
                "quantity": qty,
                "line_total": line_total,
                "unit_price": item.price,
            }
        )
        subtotal += line_total
        cart[key] = qty

    if stale:
        save_cart(session, cart)

    fiat_total = None
    ex = ExchangeRate.get_active()
    if ex and lines:
        fiat_total = (subtotal * ex.fiat_per_one_tan).quantize(Decimal("0.01"))

    return lines, subtotal, fiat_total
