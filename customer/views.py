from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, OuterRef, Prefetch, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_POST

from business.forms import CommentForm
from business.models import Category, Item, ProductAttributeValue
from business.models import Notification

from . import cart as cart_utils
from .forms import CheckoutForm, PaymentReferenceForm, SellerFulfillmentForm
from .models import Order, OrderItem
from .services import CheckoutError, cancel_order, place_order


def _category_ids_for_param(category_id):
    """Resolve category GET param to id list including children."""
    if not category_id:
        return None, None, None
    if str(category_id).isdigit():
        category = get_object_or_404(Category, id=category_id)
    else:
        category = get_object_or_404(Category, slug=category_id)
    children_ids = list(category.children.values_list("id", flat=True))
    return category, category.slug, [category.id] + children_ids


def _shop_filter_querystring(
    query=None, category_slug=None, sort_by=None, filter_status=None
):
    """Build querystring for shop links (no page). Always includes view=shop."""
    params = {}
    if query:
        params["q"] = query
    if category_slug:
        params["category"] = category_slug
    if filter_status:
        params["filter"] = filter_status
    if sort_by and sort_by not in ("", "newest"):
        params["sort"] = sort_by
    params["view"] = "shop"
    return urlencode(params)


def _item_search_q(query):
    return (
        Q(title__icontains=query)
        | Q(description__icontains=query)
        | Q(campus_location__icontains=query)
        | Q(company__name__icontains=query)
        | Q(category_obj__name__icontains=query)
    )


def search_suggest(request):
    """Live search suggestions for the storefront search boxes."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 1:
        return JsonResponse({"query": q, "items": [], "categories": []})

    items_qs = Item.objects.filter(status="active").filter(_item_search_q(q))

    category_id = request.GET.get("category")
    if category_id:
        _cat, _slug, cat_ids = _category_ids_for_param(category_id)
        if cat_ids:
            items_qs = items_qs.filter(category_obj_id__in=cat_ids)

    items_qs = items_qs.select_related("category_obj", "company").order_by(
        "-created_at"
    )[:8]
    items = []
    for item in items_qs:
        items.append(
            {
                "id": item.id,
                "title": item.title,
                "price": f"{item.price:.0f}",
                "url": reverse("customer:item_detail", args=[item.id]),
                "image": item.image.url if item.image else "",
                "meta": (
                    item.category_obj.name
                    if item.category_obj_id
                    else (item.company.name if item.company_id else "")
                ),
            }
        )

    categories = [
        {
            "id": cat.id,
            "name": cat.name,
            "url": f"{reverse('customer:home')}?category={cat.slug}&view=shop",
        }
        for cat in Category.objects.filter(name__icontains=q).order_by("name")[:4]
    ]

    return JsonResponse({"query": q, "items": items, "categories": categories})


def home(request):
    from datetime import timedelta

    from django.utils import timezone

    query = (request.GET.get("q") or "").strip() or None
    category_id = request.GET.get("category")
    filter_status = request.GET.get("filter")
    page_number = request.GET.get("page", 1)
    sort_by = request.GET.get("sort", "newest")
    reset = request.GET.get("reset")

    if reset:
        if "last_search" in request.session:
            del request.session["last_search"]
        return redirect("customer:home")

    if request.GET.get("browse"):
        return redirect("customer:home")

    sidebar_categories = list(
        Category.objects.filter(parent=None)
        .annotate(
            item_count=Count(
                "items",
                filter=Q(items__status="active"),
                distinct=True,
            )
        )
        .order_by("name")
    )
    total_active = Item.objects.filter(status="active").count()

    is_landing = not any(
        [
            query,
            category_id,
            filter_status,
            request.GET.get("sort"),
            request.GET.get("view") == "shop",
            request.GET.get("page"),
        ]
    )

    if is_landing:
        from recommend.services import get_recommendations, recommendations_as_items

        recs, personalized = get_recommendations(request, count=10)
        featured_items = recommendations_as_items(recs)
        if not featured_items:
            featured_items = list(
                Item.objects.filter(status="active", stock_quantity__gt=0)
                .select_related("category_obj", "company", "seller")
                .annotate(
                    avg_rating=Avg("company__reviews__rating"),
                    review_count=Count("company__reviews", distinct=True),
                )
                .order_by("-views", "-created_at")[:10]
            )
        items_page = list(
            Item.objects.filter(status="active")
            .select_related("category_obj", "company", "seller")
            .annotate(
                avg_rating=Avg("company__reviews__rating"),
                review_count=Count("company__reviews", distinct=True),
            )
            .order_by("-created_at")[:20]
        )
        return render(
            request,
            "business/home.html",
            {
                "is_landing": True,
                "categories": sidebar_categories,
                "sidebar_categories": sidebar_categories,
                "total_active": total_active,
                "featured_items": featured_items,
                "items": items_page,
                "recs_personalized": personalized,
                "query": None,
                "search_query": None,
                "current_category": None,
                "filter_status": None,
                "sort_by": "newest",
                "current_sort": "newest",
            },
        )

    items = Item.objects.filter(status="active").select_related(
        "category_obj", "company", "seller"
    ).annotate(
        avg_rating=Avg("company__reviews__rating"),
        review_count=Count("company__reviews", distinct=True),
    )
    current_category = None
    current_category_slug = None
    current_category_name = None

    if query:
        request.session["last_search"] = query
        items = items.filter(_item_search_q(query))
        try:
            from recommend.events import log_event_from_request
            from recommend.models import InteractionEvent

            log_event_from_request(
                request,
                InteractionEvent.SEARCH,
                metadata={"query": query[:200]},
            )
        except Exception:
            pass

    if category_id:
        category, current_category_slug, cat_ids = _category_ids_for_param(category_id)
        current_category = category
        current_category_name = category.name
        items = items.filter(category_obj_id__in=cat_ids)

    if filter_status == "new":
        # Prefer truly new items; if none this week, fall back to recent weeks,
        # then all active items — empty state only when the catalog is empty.
        week_ago = timezone.now() - timedelta(days=7)
        month_ago = timezone.now() - timedelta(days=30)
        new_qs = items.filter(created_at__gte=week_ago)
        if new_qs.exists():
            items = new_qs
        else:
            recent_qs = items.filter(created_at__gte=month_ago)
            if recent_qs.exists():
                items = recent_qs
            # else keep full `items` queryset (previous / all active)
    elif filter_status == "bestseller":
        from django.db.models import Value
        from django.db.models.functions import Coalesce

        from recommend.models import ItemFeature

        items = items.annotate(
            _purchase_count=Coalesce(
                Subquery(
                    ItemFeature.objects.filter(item_id=OuterRef("pk")).values(
                        "purchase_count"
                    )[:1]
                ),
                Value(0),
            )
        ).order_by("-_purchase_count", "-views", "-created_at")
    elif filter_status == "discount":
        items = items.filter(compare_at_price__isnull=False).exclude(
            compare_at_price__lte=0
        )

    if filter_status == "bestseller" and sort_by == "newest":
        pass
    elif sort_by in ("popular", "bestseller"):
        from django.db.models import Value
        from django.db.models.functions import Coalesce

        from recommend.models import ItemFeature

        items = items.annotate(
            _purchase_count=Coalesce(
                Subquery(
                    ItemFeature.objects.filter(item_id=OuterRef("pk")).values(
                        "purchase_count"
                    )[:1]
                ),
                Value(0),
            )
        ).order_by("-_purchase_count", "-views", "-created_at")
    elif sort_by == "recommended":
        from recommend.services import get_recommendations, recommendations_as_items

        recs, personalized = get_recommendations(request, count=120)
        rec_items = recommendations_as_items(recs)
        rec_ids = [i.id for i in rec_items]
        if rec_ids:
            # Preserve recommendation order via Case/When
            from django.db.models import Case, IntegerField, When

            preserved = Case(
                *[When(pk=pk, then=pos) for pos, pk in enumerate(rec_ids)],
                output_field=IntegerField(),
            )
            items = items.filter(pk__in=rec_ids).order_by(preserved)
        request._recs_personalized = personalized
    elif sort_by == "price_asc":
        items = items.order_by("price")
    elif sort_by == "price_desc":
        items = items.order_by("-price")
    elif sort_by == "oldest":
        items = items.order_by("created_at")
    elif sort_by == "brand_asc":
        items = items.annotate(
            brand_name=Subquery(
                ProductAttributeValue.objects.filter(
                    product=OuterRef("pk"),
                    attribute__name__in=[
                        "Brand",
                        "Make",
                        "Provider",
                        "Publisher",
                        "Company",
                    ],
                ).values("value")[:1]
            )
        ).order_by("brand_name")
    else:
        if filter_status != "bestseller":
            # Default "Recommended" shop tab (no sort / newest label): personalize when
            # user is browsing the default Recommended feed without category filters.
            if (
                not category_id
                and not filter_status
                and sort_by == "newest"
                and not query
            ):
                from recommend.services import get_recommendations, recommendations_as_items
                from django.db.models import Case, IntegerField, When

                recs, personalized = get_recommendations(request, count=120)
                rec_items = recommendations_as_items(recs)
                rec_ids = [i.id for i in rec_items]
                if rec_ids:
                    # Merge: recommended first, then remaining by created_at
                    rest = list(
                        items.exclude(pk__in=rec_ids)
                        .order_by("-created_at")
                        .values_list("id", flat=True)[:200]
                    )
                    ordered_ids = rec_ids + rest
                    preserved = Case(
                        *[When(pk=pk, then=pos) for pos, pk in enumerate(ordered_ids)],
                        output_field=IntegerField(),
                        default=len(ordered_ids),
                    )
                    items = items.filter(pk__in=ordered_ids).order_by(preserved)
                    request._recs_personalized = personalized
                else:
                    items = items.order_by("-created_at")
            else:
                items = items.order_by("-created_at")

    from recommend.services import get_recommendations, recommendations_as_items

    feat_recs, feat_personalized = get_recommendations(request, count=10)
    featured_items = recommendations_as_items(feat_recs)
    if not featured_items:
        featured_items = list(
            Item.objects.filter(status="active")
            .select_related("category_obj", "company", "seller")
            .annotate(
                avg_rating=Avg("company__reviews__rating"),
                review_count=Count("company__reviews", distinct=True),
            )
            .order_by("-views", "-created_at")[:10]
        )

    paginator = Paginator(items, 12)
    items_page = paginator.get_page(page_number)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string(
            "business/partials/items_list.html",
            {"items": items_page},
            request=request,
        )
        return JsonResponse({"html": html, "has_next": items_page.has_next()})

    filter_querystring = _shop_filter_querystring(
        query=query,
        category_slug=current_category_slug,
        sort_by=sort_by,
        filter_status=filter_status,
    )

    return render(
        request,
        "business/home.html",
        {
            "is_landing": False,
            "items": items_page,
            "featured_items": featured_items,
            "query": query,
            "search_query": query,
            "current_category": current_category_slug,
            "current_category_name": current_category_name,
            "sort_by": sort_by,
            "current_sort": sort_by,
            "filter_status": filter_status,
            "filter_querystring": filter_querystring,
            "result_count": paginator.count,
            "categories": sidebar_categories,
            "sidebar_categories": sidebar_categories,
            "total_active": total_active,
            "recs_personalized": getattr(request, "_recs_personalized", False)
            or feat_personalized,
        },
    )


def about(request):
    return render(request, "business/about.html")


def contact(request):
    return render(request, "business/contact.html")


def documentation(request):
    return render(request, "business/documentation.html")


def item_detail(request, item_id):
    item = get_object_or_404(
        Item.objects.select_related(
            "company", "category_obj", "seller", "seller__profile"
        ).prefetch_related("attribute_values__attribute", "media"),
        pk=item_id,
    )

    viewed_items = request.session.get("viewed_items", [])
    if item_id not in viewed_items and request.user != item.seller:
        item.views = F("views") + 1
        item.save(update_fields=["views"])
        item.refresh_from_db()
        viewed_items.append(item_id)
        request.session["viewed_items"] = viewed_items
        try:
            from recommend.events import log_event_from_request
            from recommend.models import InteractionEvent

            log_event_from_request(request, InteractionEvent.VIEW, item_id=item.id)
        except Exception:
            pass

    gallery = item.gallery_media()
    gallery_images = [m for m in gallery if getattr(m, "media_type", "") == "image"]
    gallery_video = next(
        (m for m in gallery if getattr(m, "media_type", "") == "video"), None
    )
    if not gallery_video and item.video:
        gallery_video = type(
            "LegacyVideo",
            (),
            {"file": item.video, "media_type": "video"},
        )()

    related_items = []
    try:
        from recommend.models import ItemSimilarity
        from recommend.services import get_recommendations, recommendations_as_items

        sim_ids = list(
            ItemSimilarity.objects.filter(item_id=item.id)
            .order_by("-score")
            .values_list("similar_item_id", flat=True)[:6]
        )
        if sim_ids:
            from django.db.models import Case, IntegerField, When

            preserved = Case(
                *[When(pk=pk, then=pos) for pos, pk in enumerate(sim_ids)],
                output_field=IntegerField(),
            )
            related_items = list(
                Item.objects.filter(
                    pk__in=sim_ids, status="active", stock_quantity__gt=0
                )
                .exclude(id=item.id)
                .order_by(preserved)[:6]
            )
        if len(related_items) < 6:
            more, _ = get_recommendations(
                request, count=6, seed_item_id=item.id, exclude_ids={item.id}
            )
            for extra in recommendations_as_items(more):
                if extra.id not in {r.id for r in related_items}:
                    related_items.append(extra)
                if len(related_items) >= 6:
                    break
    except Exception:
        related_items = []

    if len(related_items) < 6:
        filler = list(
            Item.objects.filter(category_obj=item.category_obj, status="active")
            .exclude(id__in=[item.id] + [r.id for r in related_items])
            .order_by("-views")[: 6 - len(related_items)]
        )
        related_items.extend(filler)

    comments = item.comments.all().order_by("-created_at")
    if request.method == "POST" and request.user.is_authenticated:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.item = item
            comment.user = request.user
            comment.save()
            return redirect("customer:item_detail", item_id=item.id)
    else:
        comment_form = CommentForm()

    min_qty = max(1, item.minimum_order_quantity or 1)
    if (item.stock_quantity or 0) > 0:
        qty_choices = list(range(min_qty, min(item.stock_quantity, 5) + 1))
    else:
        qty_choices = [min_qty]

    avg_rating = None
    review_count = 0
    rating_bars = []

    from django.db.models import Avg, Count
    from chat.models import DealRating
    from company.models import Review

    company_reviews = Review.objects.none()
    if item.company_id:
        company_reviews = Review.objects.filter(company_id=item.company_id)

    deal_ratings = DealRating.objects.filter(item_id=item.id)
    # Prefer combined average of company reviews + deal ratings for this item
    scores = []
    for r in company_reviews.values_list("rating", flat=True):
        scores.append(int(r))
    for r in deal_ratings.values_list("rating", flat=True):
        scores.append(int(r))
    review_count = len(scores)
    if review_count:
        avg = sum(scores) / review_count
        avg_rating = f"{avg:.1f}"
        dist = {i: 0 for i in range(1, 6)}
        for s in scores:
            dist[max(1, min(5, int(s)))] += 1
        rating_bars = [
            {
                "stars": s,
                "count": dist[s],
                "pct": int(round(100 * dist[s] / review_count)) if review_count else 0,
            }
            for s in range(5, 0, -1)
        ]

    from business.contacts import contact_bundle

    contact = contact_bundle(request, item)

    return render(
        request,
        "business/item_detail.html",
        {
            "item": item,
            "gallery_images": gallery_images,
            "gallery_video": gallery_video,
            "related_items": related_items,
            "comments": comments,
            "comment_form": comment_form,
            "qty_choices": qty_choices,
            "price_label": f"Tsh {item.price:,.0f}",
            "compare_label": (
                f"Tsh {item.compare_at_price:,.0f}"
                if item.compare_at_price and item.compare_at_price > item.price
                else None
            ),
            "item_attrs": list(item.attribute_values.select_related("attribute").all()),
            "avg_rating": avg_rating,
            "review_count": review_count,
            "rating_bars": rating_bars,
            **contact,
        },
    )


def whatsapp_share(request, item_id):
    """Legacy URL — open WhatsApp chat directly (no intermediate page)."""
    from business.contacts import contact_bundle
    from business.models import Item

    item = get_object_or_404(
        Item.objects.select_related("company", "seller", "seller__profile"),
        pk=item_id,
        status="active",
    )
    contact = contact_bundle(request, item)
    if contact.get("whatsapp_url"):
        return redirect(contact["whatsapp_url"])
    messages.warning(request, "Seller hana namba ya WhatsApp.")
    return redirect("customer:item_detail", item_id=item.id)


@login_required
def add_to_cart(request, item_id):
    qty = 1
    if request.method == "POST":
        try:
            qty = max(1, int(request.POST.get("quantity", 1)))
        except (TypeError, ValueError):
            qty = 1
    ok, err = cart_utils.add_item(request.session, item_id, qty)
    if not ok:
        messages.error(request, err or "Could not add item to cart.")
        return redirect("customer:item_detail", item_id=item_id)
    try:
        from recommend.events import log_event_from_request
        from recommend.models import InteractionEvent

        log_event_from_request(
            request,
            InteractionEvent.ADD_TO_CART,
            item_id=item_id,
            metadata={"quantity": qty},
        )
    except Exception:
        pass
    if request.method == "POST" and request.POST.get("buy_now"):
        messages.success(request, "Ready for checkout.")
        return redirect("customer:checkout")
    messages.success(request, "Added to cart.")
    return redirect("customer:view_cart")


@login_required
@require_POST
def update_cart(request, item_id):
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    ok, err = cart_utils.update_item(request.session, item_id, quantity)
    if not ok:
        messages.error(request, err or "Could not update cart.")
    return redirect("customer:view_cart")


@login_required
@require_POST
def remove_from_cart(request, item_id):
    cart_utils.remove_item(request.session, item_id)
    messages.info(request, "Item removed from cart.")
    return redirect("customer:view_cart")


@login_required
@require_POST
def clear_cart(request):
    cart_utils.clear_cart(request.session)
    messages.info(request, "Cart cleared.")
    return redirect("customer:view_cart")


@login_required
def view_cart(request):
    from business.contacts import contact_bundle

    lines, subtotal, fiat_total = cart_utils.get_cart_lines(request.session)
    for line in lines:
        line["contact"] = contact_bundle(request, line["item"])
    return render(
        request,
        "business/cart.html",
        {
            "cart_lines": lines,
            "cart_total_tan": subtotal,
            "cart_total_fiat": fiat_total,
            "cart_count": len(lines),
        },
    )


@login_required
def checkout(request):
    lines, subtotal, fiat_total = cart_utils.get_cart_lines(request.session)
    if not lines:
        messages.warning(request, "Your cart is empty.")
        return redirect("customer:view_cart")

    if request.method == "POST":
        form = CheckoutForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                order = place_order(request, form.cleaned_data)
            except CheckoutError as exc:
                messages.error(request, str(exc))
                return redirect("customer:view_cart")
            messages.success(request, f"Order {order.order_number} placed.")
            return redirect("customer:order_success", order_id=order.pk)
    else:
        form = CheckoutForm(user=request.user)

    from .services import shipping_fee

    preview_shipping = shipping_fee(Order.FULFILLMENT_PICKUP, subtotal)
    return render(
        request,
        "customer/checkout.html",
        {
            "form": form,
            "cart_lines": lines,
            "subtotal_tan": subtotal,
            "shipping_preview_tan": preview_shipping,
            "cart_total_fiat": fiat_total,
        },
    )


@login_required
def order_success(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), pk=order_id, buyer=request.user
    )
    return render(request, "customer/order_success.html", {"order": order})


@login_required
def my_orders(request):
    orders = (
        Order.objects.filter(buyer=request.user)
        .prefetch_related("items")
        .order_by("-created_at")
    )
    return render(request, "customer/order_list.html", {"orders": orders})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items", "payment"),
        pk=order_id,
        buyer=request.user,
    )
    ref_form = PaymentReferenceForm(
        initial={"payment_reference": order.payment_reference}
    )
    return render(
        request,
        "customer/order_detail.html",
        {"order": order, "ref_form": ref_form, "is_buyer": True},
    )


@login_required
@require_POST
def submit_payment_reference(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)
    form = PaymentReferenceForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid payment reference.")
        return redirect("customer:order_detail", order_id=order.pk)
    if order.payment_method not in (Order.PAY_MOMO, Order.PAY_BANK):
        messages.error(request, "This payment method does not need a reference.")
        return redirect("customer:order_detail", order_id=order.pk)
    if order.payment_status == Order.PAY_PAID:
        messages.info(request, "This order is already paid.")
        return redirect("customer:order_detail", order_id=order.pk)

    order.payment_reference = form.cleaned_data["payment_reference"]
    order.payment_status = Order.PAY_AWAITING
    order.save(update_fields=["payment_reference", "payment_status", "updated_at"])
    if hasattr(order, "payment"):
        order.payment.reference = order.payment_reference
        order.payment.save(update_fields=["reference"])

    seller_ids = set(order.items.values_list("seller_id", flat=True))
    for sid in seller_ids:
        Notification.objects.create(
            recipient_id=sid,
            message=f"Payment reference submitted for {order.order_number}",
            link=reverse("customer:seller_order_detail", args=[order.pk]),
        )
    messages.success(request, "Payment reference submitted. Awaiting seller confirmation.")
    return redirect("customer:order_detail", order_id=order.pk)


@login_required
@require_POST
def cancel_my_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)
    try:
        cancel_order(order, request.user)
        messages.success(request, f"Order {order.order_number} cancelled.")
    except CheckoutError as exc:
        messages.error(request, str(exc))
    return redirect("customer:order_detail", order_id=order.pk)


@login_required
def order_invoice(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related("items"), pk=order_id
    )
    is_buyer = order.buyer_id == request.user.id
    is_seller = order.items.filter(seller=request.user).exists()
    if not (is_buyer or is_seller or request.user.is_staff):
        messages.error(request, "You do not have access to this invoice.")
        return redirect("customer:home")
    return render(request, "customer/invoice.html", {"order": order})


@login_required
def seller_orders(request):
    items_qs = OrderItem.objects.filter(seller=request.user).select_related(
        "order", "item"
    )
    order_ids = items_qs.values_list("order_id", flat=True).distinct()
    orders = (
        Order.objects.filter(pk__in=order_ids)
        .prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.filter(seller=request.user))
        )
        .order_by("-created_at")
    )
    return render(
        request,
        "customer/seller_orders.html",
        {"orders": orders},
    )


@login_required
def seller_order_detail(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related("payment"), pk=order_id)
    my_items = list(order.items.filter(seller=request.user))
    if not my_items and not request.user.is_staff:
        messages.error(request, "You are not a seller on this order.")
        return redirect("customer:seller_orders")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "mark_paid":
            if order.payment_status != Order.PAY_PAID:
                order.mark_paid(
                    reference=request.POST.get("payment_reference")
                    or order.payment_reference,
                    user=request.user,
                )
                Notification.objects.create(
                    recipient=order.buyer,
                    message=f"Payment confirmed for order {order.order_number}",
                    link=reverse("customer:order_detail", args=[order.pk]),
                )
                messages.success(request, "Payment marked as paid.")
            return redirect("customer:seller_order_detail", order_id=order.pk)

        if action == "update_status":
            new_status = request.POST.get("status")
            allowed = {c[0] for c in Order.STATUS_CHOICES}
            if new_status in allowed and new_status != Order.STATUS_CANCELLED:
                order.status = new_status
                order.save(update_fields=["status", "updated_at"])
                Notification.objects.create(
                    recipient=order.buyer,
                    message=f"Order {order.order_number} updated to {order.get_status_display()}",
                    link=reverse("customer:order_detail", args=[order.pk]),
                )
                messages.success(request, "Order status updated.")
            return redirect("customer:seller_order_detail", order_id=order.pk)

        if action == "update_item":
            line_id = request.POST.get("item_id")
            line = get_object_or_404(
                OrderItem, pk=line_id, order=order, seller=request.user
            )
            form = SellerFulfillmentForm(request.POST)
            if form.is_valid():
                line.fulfillment_status = form.cleaned_data["fulfillment_status"]
                line.save(update_fields=["fulfillment_status"])
                # Roll up order status from seller line items when all match
                statuses = set(
                    order.items.values_list("fulfillment_status", flat=True)
                )
                if statuses == {OrderItem.FULFILLMENT_COMPLETED}:
                    order.status = Order.STATUS_COMPLETED
                    if order.payment_status != Order.PAY_PAID and order.payment_method in (
                        Order.PAY_MEETUP,
                        Order.PAY_COD,
                    ):
                        order.mark_paid(user=request.user)
                    else:
                        order.save(update_fields=["status", "updated_at"])
                elif OrderItem.FULFILLMENT_SHIPPED in statuses:
                    order.status = Order.STATUS_SHIPPED
                    order.save(update_fields=["status", "updated_at"])
                elif OrderItem.FULFILLMENT_READY in statuses:
                    order.status = Order.STATUS_READY
                    order.save(update_fields=["status", "updated_at"])
                elif OrderItem.FULFILLMENT_CONFIRMED in statuses:
                    order.status = Order.STATUS_CONFIRMED
                    order.save(update_fields=["status", "updated_at"])
                messages.success(request, "Item fulfillment updated.")
            return redirect("customer:seller_order_detail", order_id=order.pk)

    return render(
        request,
        "customer/seller_order_detail.html",
        {
            "order": order,
            "my_items": my_items,
            "status_choices": Order.STATUS_CHOICES,
            "fulfillment_choices": OrderItem.FULFILLMENT_CHOICES,
        },
    )
