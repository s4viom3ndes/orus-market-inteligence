import os
import smtplib
import logging
from email.message import EmailMessage

log = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


def is_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)


def send(to: str, subject: str, body_html: str, body_text: str | None = None) -> None:
    if not is_configured():
        log.warning("SMTP nao configurado (SMTP_USER/SMTP_PASSWORD faltando) - notificacao pulada")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.set_content(body_text or "Seu client de email nao suporta HTML.")
    msg.add_alternative(body_html, subtype="html")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)

    log.info("email enviado pra %s | subject=%s", to, subject)
