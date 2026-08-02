from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.urls import reverse

from business.models import Item, Notification
from tancoin.models import ExchangeRate

from .cart import clear_cart, get_cart_lines
from .models import Order, OrderItem, Payment


SHIPPING_FEE_TAN = Decimal("0.00")
TAX_RATE = Decimal("0.00")  # set > 0 later if needed


class CheckoutError(Exception):
    pass


def shipping_fee(fulfillment_method, subtotal):
    if fulfillment_method == Order.FULFILLMENT_DELIVERY:
        # Flat campus delivery fee; adjust via admin later if needed
        return Decimal("2.00") if subtotal > 0 else Decimal("0.00")
    return SHIPPING_FEE_TAN


@transaction.atomic
def place_order(request, cleaned_data):
    lines, subtotal, _fiat = get_cart_lines(request.session)
    if not lines:
        raise CheckoutError("Your cart is empty.")

    # Re-validate stock under lock
    locked_items = {}
    for line in lines:
        item = (
            Item.objects.select_for_update()
            .select_related("seller", "company")
            .get(pk=line["item"].pk)
        )
        if item.status != "active":
            raise CheckoutError(f"{item.title} is no longer available.")
        if item.stock_quantity < line["quantity"]:
            raise CheckoutError(
                f"Not enough stock for {item.title}. Only {item.stock_quantity} left."
            )
        if line["quantity"] < item.minimum_order_quantity:
            raise CheckoutError(
                f"{item.title} requires a minimum quantity of {item.minimum_order_quantity}."
            )
        locked_items[item.pk] = item

    shipping = shipping_fee(cleaned_data["fulfillment_method"], subtotal)
    tax = (subtotal * TAX_RATE).quantize(Decimal("0.01"))
    total = (subtotal + shipping + tax).quantize(Decimal("0.01"))

    ex = ExchangeRate.get_active()
    fiat_code = ex.fiat_currency_code if ex else "TZS"
    fiat_rate = ex.fiat_per_one_tan if ex else None
    fiat_total = (
        (total * fiat_rate).quantize(Decimal("0.01")) if fiat_rate is not None else None
    )

    payment_method = Order.PAY_COD
    payment_ref = (cleaned_data.get("payment_reference") or "").strip()
    payment_status = Order.PAY_PENDING

    order = Order.objects.create(
        order_number=Order.generate_order_number(),
        buyer=request.user,
        status=Order.STATUS_PENDING,
        payment_method=payment_method,
        payment_status=payment_status,
        fulfillment_method=cleaned_data["fulfillment_method"],
        full_name=cleaned_data["full_name"],
        phone=cleaned_data["phone"],
        email=cleaned_data.get("email") or request.user.email or "",
        campus_location=cleaned_data.get("campus_location") or "",
        address_line=cleaned_data.get("address_line") or "",
        notes=cleaned_data.get("notes") or "",
        subtotal_tan=subtotal,
        shipping_fee_tan=shipping,
        tax_tan=tax,
        total_tan=total,
        fiat_currency_code=fiat_code,
        fiat_rate_snapshot=fiat_rate,
        total_fiat_estimate=fiat_total,
        payment_reference=payment_ref,
    )

    Payment.objects.create(
        order=order,
        method=payment_method,
        amount_tan=total,
        status=Payment.STATUS_PENDING,
        reference=payment_ref,
    )

    sellers_notified = set()
    for line in lines:
        item = locked_items[line["item"].pk]
        qty = line["quantity"]
        updated = Item.objects.filter(pk=item.pk, stock_quantity__gte=qty).update(
            stock_quantity=F("stock_quantity") - qty
        )
        if not updated:
            raise CheckoutError(f"Stock changed for {item.title}. Please try again.")

        item.refresh_from_db(fields=["stock_quantity"])
        if item.stock_quantity <= 0:
            Item.objects.filter(pk=item.pk).update(status="sold")

        OrderItem.objects.create(
            order=order,
            item=item,
            seller=item.seller,
            company=item.company,
            title=item.title,
            sku=item.sku or "",
            unit_price_tan=item.price,
            quantity=qty,
            line_total_tan=(Decimal(item.price) * Decimal(qty)).quantize(
                Decimal("0.01")
            ),
        )

        try:
            from recommend.events import log_event_from_request
            from recommend.models import InteractionEvent

            log_event_from_request(
                request,
                InteractionEvent.PURCHASE,
                item_id=item.pk,
                metadata={"order_id": order.pk, "quantity": qty},
            )
        except Exception:
            pass

        # Mark legacy buyer field on last purchase for account page compatibility
        Item.objects.filter(pk=item.pk).update(buyer=request.user)

        if item.seller_id not in sellers_notified:
            sellers_notified.add(item.seller_id)
            Notification.objects.create(
                recipient=item.seller,
                message=f"New order {order.order_number} from {request.user.username}",
                link=reverse("customer:seller_order_detail", args=[order.pk]),
            )

    Notification.objects.create(
        recipient=request.user,
        message=f"Order {order.order_number} placed successfully",
        link=reverse("customer:order_detail", args=[order.pk]),
    )

    clear_cart(request.session)
    return order


@transaction.atomic
def cancel_order(order, by_user):
    if not order.can_cancel():
        raise CheckoutError("This order can no longer be cancelled.")

    order = Order.objects.select_for_update().get(pk=order.pk)
    if not order.can_cancel():
        raise CheckoutError("This order can no longer be cancelled.")

    if not order.stock_restored:
        for line in order.items.select_related("item"):
            if line.item_id:
                Item.objects.filter(pk=line.item_id).update(
                    stock_quantity=F("stock_quantity") + line.quantity,
                    status="active",
                )
            line.fulfillment_status = OrderItem.FULFILLMENT_CANCELLED
            line.save(update_fields=["fulfillment_status"])
        order.stock_restored = True

    order.status = Order.STATUS_CANCELLED
    from django.utils import timezone

    order.cancelled_at = timezone.now()
    order.save(update_fields=["status", "cancelled_at", "stock_restored", "updated_at"])

    # Notify sellers
    seller_ids = set(order.items.values_list("seller_id", flat=True))
    for sid in seller_ids:
        if sid == by_user.id:
            continue
        from django.contrib.auth.models import User

        seller = User.objects.filter(pk=sid).first()
        if seller:
            Notification.objects.create(
                recipient=seller,
                message=f"Order {order.order_number} was cancelled",
                link=reverse("customer:seller_order_detail", args=[order.pk]),
            )
    return order
