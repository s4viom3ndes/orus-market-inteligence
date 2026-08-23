import os
import json
import time
import smtplib
import logging
from email.message import EmailMessage
from src.config import USE_REMOTE_STORAGE

log = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USER


def is_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)


def send(to: str, subject: str, body_html: str, body_text: str | None = None) -> dict:
    """Envia email. Retorna dict com status pra log/notification history."""
    result = {
        "to": to,
        "subject": subject,
        "at": int(time.time()),
        "sent": False,
        "error": None,
    }

    if not is_configured():
        result["error"] = "smtp_not_configured"
        log.warning("SMTP nao configurado (SMTP_USER/SMTP_PASSWORD faltando) - notificacao pulada")
        _log_history(result)
        return result

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.set_content(body_text or "Este email requer client HTML para visualizacao.")
    msg.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        result["sent"] = True
        log.info("email enviado pra %s | subject=%s", to, subject)
    except smtplib.SMTPAuthenticationError as e:
        result["error"] = f"auth_error: {e}"
        log.error("SMTP auth falhou: %s", e)
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        log.exception("SMTP send falhou")

    _log_history(result)
    return result


def _log_history(entry: dict) -> None:
    """Grava tentativa de envio em R2 (notification_log/), pra admin auditar."""
    if not USE_REMOTE_STORAGE:
        return
    try:
        from storage.r2 import upload_bytes
        key = f"notification_log/{entry['at']}_{entry['to'].replace('@','_at_')}.json"
        upload_bytes(json.dumps(entry, indent=2).encode(), key, content_type="application/json")
    except Exception as e:
        log.warning("nao consegui gravar historico de notificacao no R2: %s", e)
