import json
import logging
from src.config import TOKEN_FILE, USE_REMOTE_STORAGE

log = logging.getLogger(__name__)

TOKEN_KEY = "state/tokens.json"


def load() -> dict:
    """Carrega tokens.json. Se USE_REMOTE_STORAGE, tenta puxar do R2 primeiro."""
    if USE_REMOTE_STORAGE:
        from storage.r2 import download_bytes
        raw = download_bytes(TOKEN_KEY)
        if raw:
            TOKEN_FILE.write_bytes(raw)
            log.info("tokens carregados do R2")
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(f"{TOKEN_FILE} nao existe (nem local nem R2). Rode o OAuth primeiro.")
    return json.loads(TOKEN_FILE.read_text())


def save(tokens: dict) -> None:
    """Grava local e, se USE_REMOTE_STORAGE, sobe pro R2."""
    payload = json.dumps(tokens, indent=2).encode()
    TOKEN_FILE.write_bytes(payload)
    if USE_REMOTE_STORAGE:
        from storage.r2 import upload_bytes
        upload_bytes(payload, TOKEN_KEY, content_type="application/json")
        log.info("tokens sincronizados no R2")
