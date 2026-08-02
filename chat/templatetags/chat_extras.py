import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_URL_RE = re.compile(r"(https?://[^\s<]+)")
_BOLD_RE = re.compile(r"\*([^*\n]+)\*")


def format_chat_message_html(text):
    """Escape text, turn *bold* into strong, and URLs into short link chips."""
    if not text:
        return ""
    html = escape(text)
    html = _BOLD_RE.sub(r"<strong>\1</strong>", html)

    def _link(match):
        url = match.group(1).rstrip(").,;]>\"'")
        lower = url.lower()
        if "/item/" in lower:
            label = "View product"
        elif "wa.me" in lower or "whatsapp" in lower:
            label = "WhatsApp"
        else:
            label = "Open link"
        return (
            f'<a class="chat-link" href="{escape(url)}" '
            f'target="_blank" rel="noopener noreferrer">{label}</a>'
        )

    html = _URL_RE.sub(_link, html)
    html = html.replace("\n", "<br>")
    return mark_safe(html)


@register.filter(name="chat_message")
def chat_message(text):
    return format_chat_message_html(text)
