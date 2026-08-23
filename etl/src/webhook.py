import json
import time
import logging
from collections import defaultdict, deque
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse

from src.config import (
    APP_ID,
    CLIENT_SECRET,
    REDIRECT_URI,
    WEBHOOK_SECRET,
    TOKEN_FILE,
    ML_API_BASE,
    ML_AUTH_BASE,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("ml-webhook")

RATE_WINDOW_SEC = 60
RATE_MAX_REQ = 120
_hits: dict[str, deque] = defaultdict(deque)

app = FastAPI()


def rate_limited(ip: str) -> bool:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > RATE_WINDOW_SEC:
        q.popleft()
    if len(q) >= RATE_MAX_REQ:
        return True
    q.append(now)
    return False


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/oauth/start", response_class=HTMLResponse)
def oauth_start():
    url = (
        f"{ML_AUTH_BASE}/authorization"
        f"?response_type=code"
        f"&client_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return HTMLResponse(
        f'<h1>Autorizar Orus no Mercado Livre</h1>'
        f'<p><a href="{url}">Clique aqui para autorizar</a></p>'
        f'<p><small>URL: {url}</small></p>'
    )


@app.post(f"/webhook/ml/{WEBHOOK_SECRET}")
async def ml_webhook(request: Request):
    ip = request.client.host if request.client else "unknown"

    if rate_limited(ip):
        raise HTTPException(status_code=429, detail="rate limited")

    payload = await request.json()

    if APP_ID and payload.get("application_id") != APP_ID:
        log.warning("rejected: application_id mismatch from %s", ip)
        raise HTTPException(status_code=403, detail="forbidden")

    log.info("ml notification: topic=%s resource=%s user=%s",
             payload.get("topic"), payload.get("resource"), payload.get("user_id"))

    return {"ok": True}


@app.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(code: str | None = None, error: str | None = None):
    if error:
        log.warning("oauth error: %s", error)
        return HTMLResponse(f"<h1>Erro na autorizacao</h1><p>{error}</p>", status_code=400)

    if not code:
        raise HTTPException(status_code=400, detail="missing code")

    if not (APP_ID and CLIENT_SECRET and REDIRECT_URI):
        raise HTTPException(status_code=500, detail="oauth env vars not configured")

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
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
        log.error("token exchange failed: %s %s", resp.status_code, resp.text)
        return HTMLResponse(
            f"<h1>Falha ao trocar code por token</h1><pre>{resp.text}</pre>",
            status_code=502,
        )

    tokens = resp.json()
    now = int(time.time())
    tokens["obtained_at"] = now
    tokens["expires_at"] = now + int(tokens.get("expires_in", 0))
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))

    has_refresh = bool(tokens.get("refresh_token"))
    log.info("tokens salvos (user_id=%s, refresh_token=%s)",
             tokens.get("user_id"), has_refresh)

    warn = ""
    if not has_refresh:
        warn = ("<p style='color:orange'><b>Atencao:</b> nao veio refresh_token. "
                "Habilite 'Autorizacao offline' no painel do app no ML e refaca este fluxo.</p>")

    return HTMLResponse(
        f"<h1>Autorizado com sucesso</h1>"
        f"<p>user_id: {tokens.get('user_id')}</p>"
        f"<p>expira em: {tokens.get('expires_in')}s</p>"
        f"{warn}"
    )
