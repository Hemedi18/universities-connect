from urllib.parse import quote

from django.urls import reverse


def normalize_tz_phone(raw):
    """Return digits suitable for tel:/WhatsApp (prefer 255…)."""
    if not raw:
        return ""
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if digits.startswith("0") and len(digits) >= 9:
        digits = "255" + digits[1:]
    return digits


def absolute_public_uri(request, location):
    """Build absolute URL; force https for tunnels / proxied hosts."""
    if location.startswith("http://") or location.startswith("https://"):
        uri = location
    else:
        uri = request.build_absolute_uri(location)
    host = ""
    try:
        host = request.get_host().lower()
    except Exception:
        pass
    forwarded = (request.META.get("HTTP_X_FORWARDED_PROTO") or "").lower()
    if (
        request.is_secure()
        or forwarded == "https"
        or "ngrok" in host
        or "loca.lt" in host
    ):
        if uri.startswith("http://"):
            uri = "https://" + uri[len("http://") :]
    return uri


def seller_contact_phone(item):
    """
    Live seller contact — prefer current profile / company number
    over a stale phone copied onto the item at post time.
    """
    try:
        profile = item.seller.profile
    except Exception:
        profile = None
    if profile and getattr(profile, "phone_number", None):
        phone = profile.phone_number.strip()
        if phone:
            return phone

    company = getattr(item, "company", None)
    if company and getattr(company, "whatsapp_number", None):
        phone = company.whatsapp_number.strip()
        if phone:
            return phone

    if getattr(item, "contact_phone", None):
        phone = item.contact_phone.strip()
        if phone:
            return phone
    return ""


def build_item_inquiry_text(item, absolute_url, image_url=""):
    """
    WhatsApp / chat body.
    Put the image URL on its own first line so WhatsApp can preview / open the photo.
    """
    lines = []
    if image_url:
        lines.append(image_url)
        lines.append("")
    lines.extend(
        [
            "Habari! Nina nia ya kununua:",
            f"*{item.title}*",
            f"Bei: {item.price:.0f}",
            absolute_url,
            "",
            "Cash on Delivery — sitalipa kabla ya kupokea mzigo.",
        ]
    )
    return "\n".join(lines)


def build_chat_inquiry_text(item):
    """Clean in-app chat copy — no raw URLs or WhatsApp *markdown*."""
    return (
        f"Habari! Nina nia ya kununua {item.title}.\n"
        f"Bei: {item.price:.0f}\n\n"
        "Cash on Delivery — sitalipa kabla ya kupokea mzigo."
    )


def build_whatsapp_url(phone, text):
    """Open WhatsApp app directly with prefilled text (+ image URL in text)."""
    digits = normalize_tz_phone(phone)
    encoded = quote(text)
    if digits:
        return f"https://wa.me/{digits}?text={encoded}"
    # No seller number — still open WhatsApp so user can pick a chat
    return f"https://wa.me/?text={encoded}"


def build_tel_url(phone):
    digits = normalize_tz_phone(phone)
    if not digits:
        return ""
    return f"tel:+{digits}"


def item_chat_url(item):
    return reverse("chat:start_chat", args=[item.seller_id]) + f"?item={item.id}"


def contact_bundle(request, item):
    """Contact URLs + display for COD flow."""
    phone = seller_contact_phone(item)
    absolute = absolute_public_uri(
        request, reverse("customer:item_detail", args=[item.id])
    )
    image_url = ""
    if getattr(item, "image", None):
        try:
            image_url = absolute_public_uri(request, item.image.url)
        except Exception:
            image_url = ""
    text = build_item_inquiry_text(item, absolute, image_url)
    return {
        "contact_phone": phone,
        "tel_url": build_tel_url(phone),
        "whatsapp_url": build_whatsapp_url(phone, text),
        "chat_url": item_chat_url(item),
        "inquiry_text": text,
        "item_image_url": image_url,
    }
