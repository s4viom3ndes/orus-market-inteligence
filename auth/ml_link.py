"""OAuth ML por usuario.

Adaptado de etl/src/webhook.py mas escopado por user_id no banco (multi-tenant).

Fluxo:
    1. authorize_url(user_id) -> URL que o cliente abre pra autorizar
    2. Cliente aceita no ML -> ML chama callback com ?code=&state=user_id
    3. exchange_code(user_id, code) -> troca por access + refresh, grava no DB
    4. get_access_token(user_id) -> le do DB, refresh automatico se expirado
"""
import os
import time
from typing import Optional
import httpx
from sqlalchemy.orm import Session as OrmSession
from auth.models import MLAccount, MLTokenSet

ML_API_BASE = "https://api.mercadolibre.com"
ML_AUTH_BASE = "https://auth.mercadolivre.com.br"

APP_ID = int(os.getenv("ML_APP_ID", "0"))
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("ML_REDIRECT_URI_USER", os.getenv("ML_REDIRECT_URI", ""))

REFRESH_MARGIN_SEC = 300


class MLLinkError(Exception):
    pass


def authorize_url(user_id: int) -> str:
    """Retorna URL de autorizacao ML. `state=user_id` volta no callback."""
    if not APP_ID:
        raise MLLinkError("ML_APP_ID nao configurado")
    return (
        f"{ML_AUTH_BASE}/authorization"
        f"?response_type=code"
        f"&client_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state=user_{user_id}"
    )


def exchange_code(db: OrmSession, user_id: int, code: str) -> MLAccount:
    """Troca `code` do callback OAuth por access+refresh e persiste."""
    if not (APP_ID and CLIENT_SECRET and REDIRECT_URI):
        raise MLLinkError("env vars ML_APP_ID/CLIENT_SECRET/REDIRECT_URI faltando")

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{ML_API_BASE}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": APP_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        raise MLLinkError(f"token exchange falhou {resp.status_code}: {resp.text}")

    tok = resp.json()
    now = int(time.time())

    with httpx.Client(timeout=15) as client:
        me = client.get(f"{ML_API_BASE}/users/me",
                        headers={"Authorization": f"Bearer {tok['access_token']}"})
    if me.status_code != 200:
        raise MLLinkError(f"/users/me falhou {me.status_code}: {me.text}")
    me_data = me.json()

    account = db.query(MLAccount).filter_by(user_id=user_id, ml_user_id=me_data["id"]).first()
    if not account:
        account = MLAccount(
            user_id=user_id,
            ml_user_id=me_data["id"],
            ml_nickname=me_data.get("nickname"),
            ml_email=me_data.get("email"),
            site_id=me_data.get("site_id", "MLB"),
        )
        db.add(account)
        db.flush()

    token_set = db.query(MLTokenSet).filter_by(ml_account_id=account.id).first()
    if not token_set:
        token_set = MLTokenSet(ml_account_id=account.id)
        db.add(token_set)
    token_set.access_token = tok["access_token"]
    token_set.refresh_token = tok.get("refresh_token")
    token_set.token_type = tok.get("token_type", "Bearer")
    token_set.scope = tok.get("scope")
    token_set.obtained_at = now
    token_set.expires_at = now + int(tok.get("expires_in", 21600))
    db.commit()
    return account


def get_access_token(db: OrmSession, ml_account_id: int) -> str:
    """Le token do DB, refresh automatico se estiver perto de expirar."""
    ts = db.query(MLTokenSet).filter_by(ml_account_id=ml_account_id).first()
    if not ts:
        raise MLLinkError("nenhum token pra esse ml_account")

    if time.time() < ts.expires_at - REFRESH_MARGIN_SEC:
        return ts.access_token

    if not ts.refresh_token:
        raise MLLinkError("token expirado e sem refresh_token — cliente precisa relincar")

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{ML_API_BASE}/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": APP_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": ts.refresh_token,
            },
        )
    if resp.status_code != 200:
        raise MLLinkError(f"refresh falhou {resp.status_code}: {resp.text}")
    tok = resp.json()
    now = int(time.time())
    ts.access_token = tok["access_token"]
    ts.refresh_token = tok.get("refresh_token") or ts.refresh_token
    ts.obtained_at = now
    ts.expires_at = now + int(tok.get("expires_in", 21600))
    db.commit()
    return ts.access_token
