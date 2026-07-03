import os
import html as html_lib
from app.services.auth.auth_service import AuthService
from app.repositories.support_repository import SupportRepository
from app.utils.logger import get_logger

logger = get_logger("support_service")

CATEGORY_LABELS = {
    "general": "General Inquiry",
    "bug": "Bug Report",
    "feature": "Feature Request",
    "account": "Account or Login Issue",
}


class SupportService:
    @staticmethod
    def _support_inbox() -> str:
        """The address that receives support tickets."""
        return (
            os.environ.get("SUPPORT_EMAIL")
            or os.environ.get("SMTP_USER")
            or "ai.invexo@outlook.com"
        )

    @staticmethod
    def submit_ticket(name: str, email: str, category: str, subject: str,
                      message: str, user_id: int | None = None) -> bool:
        """
        Persists a support ticket, then (best-effort) emails the team inbox and
        an acknowledgement to the user. Returns True once the ticket is stored;
        email delivery does not gate success since the ticket is safely recorded.
        Returns False only if the ticket could not be persisted.
        """
        category_label = CATEGORY_LABELS.get(category, "General Inquiry")
        inbox = SupportService._support_inbox()

        # ── 1. Persist the ticket first (source of truth) ───────────
        ticket_id = SupportRepository.create_ticket(
            name=name, email=email, category=category,
            subject=subject, message=message, user_id=user_id,
        )
        if ticket_id is None:
            logger.error(f"[Support] Could not persist ticket from {email}")
            return False

        # ── 2. Notify the support team ──────────────────────────────
        team_subject = f"[Invexo Support · {category_label}] {subject}"
        team_text = (
            f"New support request received via Invexo.\n\n"
            f"Category: {category_label}\n"
            f"Name: {name}\n"
            f"Email: {email}\n"
            f"Subject: {subject}\n\n"
            f"Message:\n{message}\n"
        )
        team_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0b0f19;color:#f3f4f6;padding:24px;">
  <div style="max-width:600px;margin:0 auto;background:#111827;border:1px solid #1e293b;border-radius:14px;padding:28px;">
    <h2 style="margin:0 0 16px;color:#38bdf8;">New Support Request</h2>
    <table style="width:100%;border-collapse:collapse;font-size:14px;color:#cbd5e1;">
      <tr><td style="padding:6px 0;color:#94a3b8;width:110px;">Category</td><td style="padding:6px 0;">{html_lib.escape(category_label)}</td></tr>
      <tr><td style="padding:6px 0;color:#94a3b8;">Name</td><td style="padding:6px 0;">{html_lib.escape(name)}</td></tr>
      <tr><td style="padding:6px 0;color:#94a3b8;">Email</td><td style="padding:6px 0;"><a href="mailto:{html_lib.escape(email)}" style="color:#38bdf8;">{html_lib.escape(email)}</a></td></tr>
      <tr><td style="padding:6px 0;color:#94a3b8;">Subject</td><td style="padding:6px 0;">{html_lib.escape(subject)}</td></tr>
    </table>
    <div style="margin-top:18px;padding-top:18px;border-top:1px solid #1e293b;font-size:14px;line-height:1.6;color:#e2e8f0;white-space:pre-wrap;">{html_lib.escape(message)}</div>
  </div>
</body>
</html>"""

        delivered = False
        try:
            delivered = AuthService._send_email(
                inbox, team_subject, team_text, html=team_html, reply_to=email
            )
        except Exception as e:
            logger.error(f"[Support] Error emailing team for ticket {ticket_id}: {e}")

        if delivered:
            logger.info(f"[Support] Ticket {ticket_id} from {email} delivered to {inbox}")
        else:
            logger.error(f"[Support] Ticket {ticket_id} stored but email to {inbox} failed")
        SupportRepository.mark_delivered(ticket_id, delivered)

        # ── 3. Acknowledge to the user (best-effort) ────────────────
        try:
            ack_subject = "We've received your message — Invexo Support"
            ack_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:#0b0f19;color:#f3f4f6;padding:24px;">
  <div style="max-width:600px;margin:0 auto;background:linear-gradient(135deg,#111827,#0f172a);border:1px solid #1e293b;border-radius:16px;padding:36px;">
    <div style="font-size:24px;font-weight:800;background:linear-gradient(to right,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">INVEXO</div>
    <h1 style="font-size:20px;color:#ffffff;margin:18px 0 12px;">Thanks for reaching out, {html_lib.escape(name)}!</h1>
    <p style="font-size:15px;line-height:1.6;color:#cbd5e1;">
      We've received your message and our team will get back to you as soon as possible.
      Here's a copy of what you sent us:
    </p>
    <div style="margin:20px 0;padding:16px;background:#0f172a;border:1px solid #1e293b;border-radius:10px;">
      <p style="margin:0 0 8px;font-size:13px;color:#94a3b8;">Subject</p>
      <p style="margin:0 0 16px;font-size:14px;color:#e2e8f0;">{html_lib.escape(subject)}</p>
      <p style="margin:0 0 8px;font-size:13px;color:#94a3b8;">Message</p>
      <p style="margin:0;font-size:14px;color:#e2e8f0;line-height:1.6;white-space:pre-wrap;">{html_lib.escape(message)}</p>
    </div>
    <p style="font-size:13px;color:#64748b;margin-top:24px;">— The Invexo Team</p>
  </div>
</body>
</html>"""
            ack_text = (
                f"Hi {name},\n\n"
                f"We've received your message and our team will get back to you as soon as possible.\n\n"
                f"Subject: {subject}\n"
                f"Message:\n{message}\n\n"
                f"— The Invexo Team"
            )
            AuthService._send_email(email, ack_subject, ack_text, html=ack_html)
        except Exception as e:
            logger.error(f"[Support] Failed to send acknowledgement to {email}: {e}")

        return True
