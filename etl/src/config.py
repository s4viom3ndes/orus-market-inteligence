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

# A watchlist tem prioridade sobre as folhas descobertas: o que esta aqui e
# coletado mesmo que o walker de categorias nao chegue la. E o unico jeito de
# garantir cobertura das categorias onde o cliente realmente vende.
WATCHLIST_CATEGORIES: list[str] = [
    # --- categorias da carteira do cliente ativo ---
    "MLB193633",  # Saca Rolhas e Abridores
    "MLB118026",  # Caixas e Estojos
    "MLB186365",  # Cabides
    "MLB409094",  # Luminarias de Sal
    "MLB45425",   # Campainhas
    "MLB30163",   # Paquimetros
    "MLB277954",  # Bolas para Piscinas
    # --- contexto de mercado ---
    "MLB193807",  # Raladores
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
