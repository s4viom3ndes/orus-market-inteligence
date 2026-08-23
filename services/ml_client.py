import time
import logging
import httpx
from src.config import APP_ID, CLIENT_SECRET, ML_API_BASE
from services import token_store

log = logging.getLogger(__name__)

REFRESH_MARGIN_SEC = 300


class TokenError(Exception):
    pass


def _read_tokens() -> dict:
    try:
        return token_store.load()
    except FileNotFoundError as e:
        raise TokenError(str(e))


def _write_tokens(tokens: dict) -> None:
    tokens["obtained_at"] = int(time.time())
    tokens["expires_at"] = tokens["obtained_at"] + int(tokens.get("expires_in", 0))
    token_store.save(tokens)


def _is_expired(tokens: dict) -> bool:
    expires_at = tokens.get("expires_at")
    if not expires_at:
        expires_at = tokens.get("obtained_at", 0) + tokens.get("expires_in", 0)
    return time.time() >= expires_at - REFRESH_MARGIN_SEC


def _refresh(refresh_token: str) -> dict:
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            f"{ML_API_BASE}/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": APP_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh_token,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        raise TokenError(f"refresh falhou: {resp.status_code} {resp.text}")
    return resp.json()


def get_access_token() -> str:
    tokens = _read_tokens()

    if not _is_expired(tokens):
        return tokens["access_token"]

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise TokenError(
            "access_token expirado e nao ha refresh_token. "
            "Refaca a autorizacao OAuth com scope offline_access."
        )

    log.info("access_token expirado, renovando...")
    new_tokens = _refresh(refresh_token)
    _write_tokens(new_tokens)
    return new_tokens["access_token"]


class MLClient:
    def __init__(self):
        self._client = httpx.Client(timeout=30, base_url=ML_API_BASE)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {get_access_token()}"}

    def get(self, path: str, **params) -> dict:
        r = self._client.get(path, headers=self._headers(), params=params)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, json: dict | None = None) -> dict:
        r = self._client.post(path, headers=self._headers(), json=json)
        r.raise_for_status()
        return r.json()

    def close(self):
        self._client.close()
