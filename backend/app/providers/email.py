"""Email sending behind one interface: SMTP (Mailpit in development) or in-memory (tests)."""

from __future__ import annotations

from dataclasses import dataclass, field
from email.message import EmailMessage as MimeMessage
from typing import Protocol

import aiosmtplib

from app.core.config import Settings


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str


class EmailSender(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def send(self, message: OutgoingEmail) -> None:
        mime = MimeMessage()
        mime["From"] = self.settings.email_from
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.text)
        mime.add_alternative(message.html, subtype="html")
        password = (
            self.settings.smtp_password.get_secret_value() if self.settings.smtp_password else None
        )
        await aiosmtplib.send(
            mime,
            hostname=self.settings.smtp_host,
            port=self.settings.smtp_port,
            username=self.settings.smtp_username,
            password=password,
            start_tls=self.settings.smtp_starttls,
            timeout=15,
        )


@dataclass
class MemoryEmailSender:
    outbox: list[OutgoingEmail] = field(default_factory=list)

    async def send(self, message: OutgoingEmail) -> None:
        self.outbox.append(message)


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "memory":
        return MemoryEmailSender()
    return SmtpEmailSender(settings)
