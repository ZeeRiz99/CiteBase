"""Transactional email templates. Rendered at send time from a job payload."""

from __future__ import annotations

from html import escape
from typing import Any

from app.core.config import Settings
from app.providers.email import OutgoingEmail

VERIFY_EMAIL = "verify_email"
RESET_PASSWORD = "reset_password"  # noqa: S105 - template name, not a secret


def _layout(settings: Settings, heading: str, body_html: str, link: str, cta: str) -> str:
    name = escape(settings.product_name)
    return f"""<!doctype html>
<html><body style="margin:0;background:#f4f6fa;font-family:Inter,Segoe UI,Arial,sans-serif;color:#0b1b33">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:32px 16px">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:520px;background:#ffffff;border-radius:12px;padding:32px">
        <tr><td style="font-size:18px;font-weight:700;color:#0b1b33;padding-bottom:16px">{name}</td></tr>
        <tr><td style="font-size:20px;font-weight:600;padding-bottom:12px">{escape(heading)}</td></tr>
        <tr><td style="font-size:15px;line-height:1.6;color:#334155;padding-bottom:24px">{body_html}</td></tr>
        <tr><td><a href="{escape(link, quote=True)}" style="display:inline-block;background:#0f766e;color:#ffffff;text-decoration:none;padding:12px 20px;border-radius:8px;font-weight:600">{escape(cta)}</a></td></tr>
        <tr><td style="font-size:12px;color:#64748b;padding-top:24px;word-break:break-all">If the button does not work, open this link: {escape(link)}</td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def render(template: str, context: dict[str, Any], settings: Settings) -> OutgoingEmail:
    to = str(context["to"])
    name = str(context.get("name") or "there")
    link = str(context["link"])
    product = settings.product_name

    if template == VERIFY_EMAIL:
        hours = settings.email_verification_ttl_hours
        text = (
            f"Hi {name},\n\nConfirm your email address for {product}:\n{link}\n\n"
            f"This link expires in {hours} hours. If you did not sign up, ignore this email.\n"
        )
        html = _layout(
            settings,
            "Confirm your email address",
            f"Hi {escape(name)}, confirm your email to finish setting up {escape(product)}. "
            f"This link expires in {hours} hours. If you did not sign up, you can ignore this email.",
            link,
            "Confirm email",
        )
        return OutgoingEmail(
            to=to, subject=f"Confirm your email for {product}", text=text, html=html
        )

    if template == RESET_PASSWORD:
        minutes = settings.password_reset_ttl_minutes
        text = (
            f"Hi {name},\n\nReset your {product} password:\n{link}\n\n"
            f"This link expires in {minutes} minutes. If you did not ask for this, ignore this email.\n"
        )
        html = _layout(
            settings,
            "Reset your password",
            f"Hi {escape(name)}, use the button below to choose a new password. "
            f"This link expires in {minutes} minutes. If you did not ask for this, you can ignore this email.",
            link,
            "Reset password",
        )
        return OutgoingEmail(to=to, subject=f"Reset your {product} password", text=text, html=html)

    raise ValueError(f"Unknown email template: {template}")
