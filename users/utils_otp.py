import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_SITE_URL = getattr(settings, "SITE_URL", "https://uconnect.edusphere.co.tz")


def send_otp_email(email, otp_code, purpose="registration", username=""):
    """
    Sends a 6-digit OTP code to the specified email address using a modern,
    responsive HTML email template with a plain-text fallback.
    """
    clean_email = email.strip().lower()
    from_email = getattr(
        settings,
        "DEFAULT_FROM_EMAIL",
        "U-Connect Security <otp@uconnect.edusphere.co.tz>"
    )

    if purpose == "registration":
        subject = f"[{otp_code}] Thibitisha Akaunti Yako • U-Connect Verification Code"
        action_url = f"{BASE_SITE_URL}/users/verify-otp/"
        greeting = f"Habari {username}," if username else "Habari,"
        plain_message = (
            f"{greeting}\n\n"
            f"Asante kwa kujiunga na U-Connect!\n"
            f"Nambari yako ya uthibitisho (OTP Code) ni:\n\n"
            f"    ========================\n"
            f"    VERIFICATION CODE: {otp_code}\n"
            f"    ========================\n\n"
            f"Nambari hii inatumika kwa dakika 10 tu.\n"
            f"Unganisha au fungua ukurasa huu kukamilisha: {action_url}\n\n"
            f"Kamwe usimpe mtu yeyote nambari hii ya siri.\n\n"
            f"— The U-Connect Security Team"
        )
    else:  # password_reset
        subject = f"[{otp_code}] Badilisha Nenosiri • U-Connect Password Reset Code"
        action_url = f"{BASE_SITE_URL}/password-reset/verify/"
        greeting = f"Habari {username}," if username else "Habari,"
        plain_message = (
            f"{greeting}\n\n"
            f"Tumepokea ombi la kubadilisha nenosiri kwenye akaunti yako ya U-Connect.\n"
            f"Nambari yako ya kubadilisha nenosiri (OTP Code) ni:\n\n"
            f"    ========================\n"
            f"    RESET CODE: {otp_code}\n"
            f"    ========================\n\n"
            f"Nambari hii inatumika kwa dakika 10 tu.\n"
            f"Fungua ukurasa huu kuweka nenosiri jipya: {action_url}\n\n"
            f"Kama hukufanya ombi hili, tafadhali puuza barua pepe hii; akaunti yako iko salama.\n\n"
            f"— The U-Connect Security Team"
        )

    context = {
        "subject": subject,
        "purpose": purpose,
        "username": username,
        "otp_code": otp_code,
        "action_url": action_url,
        "site_url": BASE_SITE_URL,
    }

    try:
        html_content = render_to_string("emails/otp_email.html", context)
    except Exception as render_err:
        logger.warning(f"Could not render HTML email template: {render_err}. Falling back to plain text.")
        html_content = None

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=from_email,
            to=[clean_email],
        )
        if html_content:
            msg.attach_alternative(html_content, "text/html")

        msg.send(fail_silently=False)
        logger.info(f"HTML OTP email successfully sent to {clean_email} ({purpose})")
        return True
    except Exception as e:
        logger.error(f"Failed to send HTML OTP email to {clean_email}: {e}")
        return False
