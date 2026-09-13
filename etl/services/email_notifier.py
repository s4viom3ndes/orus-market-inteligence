import os
import json
import time
import smtplib
import logging
from email.message import EmailMessage
from src.config import USE_REMOTE_STORAGE

log = logging.getLogger(__name__)

# GH Actions injeta secret ausente como string vazia, entao o default do getenv
# nunca entra - usar `or` pra tratar "" como nao-definido.
SMTP_HOST = os.getenv("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = int(os.getenv("SMTP_PORT") or "587")
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM") or SMTP_USER


def is_configured() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)


def destinatarios(to) -> list[str]:
    """Destinatario do job + os extras do secret NOTIFY_EMAILS, sem repetir.

    Os extras vem de secret e nao do repo porque o repositorio e publico, e
    email de terceiro nao pode ficar versionado. Lido a cada chamada, nao no
    import, para que trocar o secret nao exija reiniciar nada.
    """
    brutos = [to] if isinstance(to, str) or to is None else list(to)
    brutos.append(os.getenv("NOTIFY_EMAILS") or "")
    vistos, saida = set(), []
    for item in brutos:
        for email in (item or "").split(","):
            email = email.strip()
            if email and email.lower() not in vistos:
                vistos.add(email.lower())
                saida.append(email)
    return saida


def send(to, subject: str, body_html: str, body_text: str | None = None) -> dict:
    """Envia email. Retorna dict com status pra log/notification history."""
    lista = destinatarios(to)
    result = {
        "to": ", ".join(lista),
        "subject": subject,
        "at": int(time.time()),
        "sent": False,
        "error": None,
    }

    if not lista:
        result["error"] = "sem_destinatario"
        log.warning("nenhum destinatario definido - notificacao pulada")
        _log_history(result)
        return result

    if not is_configured():
        result["error"] = "smtp_not_configured"
        log.warning("SMTP nao configurado (SMTP_USER/SMTP_PASSWORD faltando) - notificacao pulada")
        _log_history(result)
        return result

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = result["to"]
    msg.set_content(body_text or "Este email requer client HTML para visualizacao.")
    msg.add_alternative(body_html, subtype="html")

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
        result["sent"] = True
        log.info("email enviado pra %s | subject=%s", result["to"], subject)
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
        # com varios destinatarios, a chave usa so o primeiro: virgula e espaco
        # nao entram em nome de objeto. A lista completa fica dentro do JSON.
        primeiro = (entry.get("to") or "sem_destinatario").split(",")[0].strip()
        seguro = "".join(c if c.isalnum() or c in "._-" else "_"
                         for c in primeiro.replace("@", "_at_"))
        key = f"notification_log/{entry['at']}_{seguro}.json"
        upload_bytes(json.dumps(entry, indent=2).encode(), key, content_type="application/json")
    except Exception as e:
        log.warning("nao consegui gravar historico de notificacao no R2: %s", e)
