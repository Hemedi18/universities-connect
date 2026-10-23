import traceback
import logging
from django.utils.deprecation import MiddlewareMixin
from .models import SystemErrorLog

logger = logging.getLogger(__name__)


class SystemErrorCaptureMiddleware(MiddlewareMixin):
    """
    Automatically captures unhandled 500 exceptions across the website
    and saves them to the SystemErrorLog database table so admins can
    instantly inspect, troubleshoot, and resolve issues from the Command Center.
    """

    def process_exception(self, request, exception):
        try:
            user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
            ip = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip() or request.META.get("REMOTE_ADDR")
            tb = traceback.format_exc()

            SystemErrorLog.objects.create(
                level="ERROR",
                message=str(exception),
                endpoint=request.path[:250],
                ip_address=ip if len(str(ip)) <= 50 else None,
                user=user,
                traceback=tb,
                is_resolved=False,
            )
        except Exception as e:
            logger.error(f"Failed to record SystemErrorLog: {e}")

        # Let Django proceed with standard 500 handling
        return None
