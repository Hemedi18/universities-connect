from .models import Notification
from customer.cart import cart_item_count


def notifications(request):
    ctx = {"cart_item_count": 0}
    if request.user.is_authenticated:
        ctx["unread_notifications_count"] = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        ctx["cart_item_count"] = cart_item_count(request.session)
    else:
        ctx["unread_notifications_count"] = 0
    return ctx
