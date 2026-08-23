import os
from pathlib import Path
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).parent.parent.parent
ETL_ROOT = Path(__file__).parent.parent

load_dotenv(REPO_ROOT / ".env")

PROJECT_ROOT = ETL_ROOT
TOKEN_FILE = REPO_ROOT / "tokens.json"

APP_ID = int(os.getenv("ML_APP_ID", "0"))
CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("ML_REDIRECT_URI", "")
WEBHOOK_SECRET = os.getenv("ML_WEBHOOK_SECRET", "troque-este-segredo-agora")

ML_API_BASE = "https://api.mercadolibre.com"
ML_AUTH_BASE = "https://auth.mercadolivre.com.br"

WATCHLIST_SELLERS: list[int] = [
    2692951735,
]

WATCHLIST_CATEGORIES: list[str] = [
    "MLB193633",  # Saca Rolhas e Abridores
    "MLB193807",  # Raladores
    "MLB186365",  # Cabides
    "MLB1586",    # Luminarias de Mesa
]

# --- Storage remoto (Cloudflare R2 ou qualquer S3-compat) ---
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET = os.getenv("R2_BUCKET", "orus-data")

USE_REMOTE_STORAGE = bool(R2_ENDPOINT and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY)


def authorization_url() -> str:
    return (
        f"{ML_AUTH_BASE}/authorization"
        f"?response_type=code"
        f"&client_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
