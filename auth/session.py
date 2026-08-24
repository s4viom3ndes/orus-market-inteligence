"""Session cookie assinado com itsdangerous.

Streamlit nao tem cookie API nativo. Solucao:
- Gera token opaco (UUID) armazenado em `sessions` table + cookie assinado no browser
- Cookie: nome=orus_sess, valor=serializer.dumps(session_id)
- Verifica: unserialize + lookup em DB + check expires_at

Pra manipular cookies em Streamlit: usar streamlit-cookies-manager (adicionar
depois quando ativar) OU passar session via query param (dev only).
"""
import os
import secrets
from datetime import datetime, timedelta
from itsdangerous import URLSafeSerializer, BadSignature

SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "dev-secret-change-me-in-prod")
SESSION_TTL_HOURS = int(os.getenv("AUTH_SESSION_TTL_HOURS", "168"))
COOKIE_NAME = "orus_sess"

_serializer = URLSafeSerializer(SECRET_KEY, salt="orus.session")


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def new_expires_at() -> datetime:
    return datetime.utcnow() + timedelta(hours=SESSION_TTL_HOURS)


def sign(session_id: str) -> str:
    return _serializer.dumps(session_id)


def unsign(signed: str) -> str | None:
    try:
        return _serializer.loads(signed)
    except BadSignature:
        return None
