import email
from email.header import decode_header
import imaplib
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.conf import settings

logger = logging.getLogger(__name__)

# Dedicated cPanel Mailboxes
MAIL_SERVER_HOST = getattr(settings, "EMAIL_HOST", "brandy.hostns.io")
IMAP_PORT = 993
SMTP_PORT = getattr(settings, "EMAIL_PORT", 465)

CPANEL_ACCOUNTS = {
    "support": {
        "email": "support@uconnect.edusphere.co.tz",
        "password": "UConn#Sup2026!9vM",
        "name": "U-Connect Support",
        "badge_color": "#059669",
        "description": "Customer care, inquiries, and dispute resolution",
    },
    "otp": {
        "email": "otp@uconnect.edusphere.co.tz",
        "password": "Otp!Connect2026#Secure",
        "name": "U-Connect Security",
        "badge_color": "#dc2626",
        "description": "Registration OTPs, security alerts & password resets",
    },
    "updates": {
        "email": "updates@uconnect.edusphere.co.tz",
        "password": "UConn#Upd2026!4wQ",
        "name": "U-Connect Updates",
        "badge_color": "#2563eb",
        "description": "System notices, new listings & order confirmations",
    },
    "marketing": {
        "email": "marketing@uconnect.edusphere.co.tz",
        "password": "UConn#Mkt2026!8zR",
        "name": "U-Connect Marketing",
        "badge_color": "#7c3aed",
        "description": "Campaigns, promotional announcements & campus news",
    },
}


def _decode_str(header_val):
    if not header_val:
        return ""
    decoded_fragments = decode_header(header_val)
    parts = []
    for raw_bytes, enc in decoded_fragments:
        if isinstance(raw_bytes, bytes):
            try:
                parts.append(raw_bytes.decode(enc or "utf-8", errors="replace"))
            except Exception:
                parts.append(raw_bytes.decode("latin-1", errors="replace"))
        else:
            parts.append(str(raw_bytes))
    return " ".join(parts).strip()


def fetch_account_emails(account_key="support", folder="INBOX", limit=15):
    """
    Connects via IMAP SSL to brandy.hostns.io, selects folder, and returns
    the latest emails with subject, sender, date, snippet, and preview.
    """
    account_info = CPANEL_ACCOUNTS.get(account_key)
    if not account_info:
        return {"status": "error", "message": f"Invalid account: {account_key}"}

    ctx = ssl.create_default_context()
    emails_list = []

    try:
        mail = imaplib.IMAP4_SSL(MAIL_SERVER_HOST, IMAP_PORT, ssl_context=ctx)
        mail.login(account_info["email"], account_info["password"])
        mail.select(folder)

        status, data = mail.search(None, "ALL")
        if status != "OK" or not data[0]:
            mail.logout()
            return {"status": "success", "account": account_info, "emails": [], "count": 0}

        msg_ids = data[0].split()
        total_count = len(msg_ids)
        # Get latest first
        latest_ids = msg_ids[-limit:] if total_count > limit else msg_ids
        latest_ids.reverse()

        for msg_id in latest_ids:
            try:
                res, fetch_data = mail.fetch(msg_id, "(RFC822)")
                if res != "OK":
                    continue

                raw_email = fetch_data[0][1]
                msg = email.message_from_bytes(raw_email)

                subject = _decode_str(msg.get("Subject", "(No Subject)"))
                from_addr = _decode_str(msg.get("From", "(Unknown Sender)"))
                to_addr = _decode_str(msg.get("To", account_info["email"]))
                date_str = msg.get("Date", "")

                body_text = ""
                body_html = ""

                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition", ""))
                        if "attachment" in content_disposition:
                            continue
                        try:
                            payload = part.get_payload(decode=True)
                            charset = part.get_content_charset() or "utf-8"
                            if payload:
                                decoded_content = payload.decode(charset, errors="replace")
                                if content_type == "text/plain" and not body_text:
                                    body_text = decoded_content
                                elif content_type == "text/html" and not body_html:
                                    body_html = decoded_content
                        except Exception:
                            pass
                else:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or "utf-8"
                    if payload:
                        decoded_content = payload.decode(charset, errors="replace")
                        if msg.get_content_type() == "text/html":
                            body_html = decoded_content
                        else:
                            body_text = decoded_content

                snippet = (body_text or body_html)[:160].replace("\n", " ").strip()

                emails_list.append({
                    "id": msg_id.decode("utf-8") if isinstance(msg_id, bytes) else str(msg_id),
                    "subject": subject,
                    "from": from_addr,
                    "to": to_addr,
                    "date": date_str,
                    "snippet": snippet,
                    "body_text": body_text[:4000],
                    "body_html": body_html[:15000],
                    "has_html": bool(body_html),
                })
            except Exception as parse_e:
                logger.warning(f"Error parsing email message {msg_id}: {parse_e}")
                continue

        mail.logout()
        return {
            "status": "success",
            "account": account_info,
            "emails": emails_list,
            "total_count": total_count,
        }

    except Exception as e:
        logger.error(f"IMAP connection error for {account_info['email']}: {e}")
        return {
            "status": "error",
            "message": str(e),
            "account": account_info,
            "emails": [],
            "total_count": 0,
        }


def send_cpanel_email(account_key, to_email, subject, body_html, body_text=None):
    """
    Sends an outgoing HTML email from the selected cPanel account via SMTP SSL.
    """
    account_info = CPANEL_ACCOUNTS.get(account_key)
    if not account_info:
        return False, f"Invalid sender account: {account_key}"

    sender_email = account_info["email"]
    sender_name = account_info["name"]

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{sender_email}>"
    msg["To"] = to_email

    if not body_text:
        # Strip simple tags for plain text fallback
        import re
        body_text = re.sub(r"<[^>]+>", " ", body_html).strip()

    part1 = MIMEText(body_text, "plain", "utf-8")
    part2 = MIMEText(body_html, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(MAIL_SERVER_HOST, SMTP_PORT, context=ctx, timeout=12) as server:
            server.login(sender_email, account_info["password"])
            server.sendmail(sender_email, [to_email], msg.as_string())
        logger.info(f"Dashboard email sent from {sender_email} to {to_email}")
        return True, "Email sent successfully"
    except Exception as e:
        logger.error(f"Failed to send email from {sender_email}: {e}")
        return False, str(e)
