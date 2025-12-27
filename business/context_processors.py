from .models import Notification

def notifications(request):
    if request.user.is_authenticated:
        return {'unread_notifications_count': Notification.objects.filter(recipient=request.user, is_read=False).count()}
    return {}