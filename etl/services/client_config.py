"""Carrega configuracao de cliente a partir do R2.

Por que nao no git: o repositorio e publico, e config de cliente carrega
informacao comercial - carteira, precos, e o mapeamento de catalogos concorrentes
que e resultado da nossa analise. O R2 ja e privado e as credenciais ja estao nos
secrets, entao ele e o lugar certo.

Precedencia:
  1. R2 em state/clients/{nome}.yaml  - fonte de verdade em producao
  2. arquivo local etl/config/client_{nome}.yaml  - so para desenvolvimento,
     e esse caminho esta no .gitignore

`push()` sobe um arquivo local para o R2; e como um cliente novo entra.
"""
import logging

import yaml

from src.config import ETL_ROOT, USE_REMOTE_STORAGE

log = logging.getLogger(__name__)

PREFIXO = "state/clients"
LOCAL_DIR = ETL_ROOT / "config"


def _chave(nome: str) -> str:
    return f"{PREFIXO}/{nome}.yaml"


def _local(nome: str):
    return LOCAL_DIR / f"client_{nome}.yaml"


def load(nome: str) -> dict:
    """Config do cliente. R2 primeiro, local como fallback de desenvolvimento."""
    if USE_REMOTE_STORAGE:
        try:
            from storage.r2 import download_bytes
            raw = download_bytes(_chave(nome))
            if raw:
                log.info("config de %s carregado do R2", nome)
                return yaml.safe_load(raw)
            log.warning("config de %s ausente no R2 (%s)", nome, _chave(nome))
        except Exception as e:
            log.warning("falha lendo config de %s no R2: %s", nome, e)

    caminho = _local(nome)
    if caminho.exists():
        log.info("config de %s carregado do arquivo local", nome)
        return yaml.safe_load(caminho.read_text(encoding="utf-8"))

    raise FileNotFoundError(
        f"config do cliente '{nome}' nao encontrado nem no R2 ({_chave(nome)}) "
        f"nem em {caminho}. Use client_config.push() para enviar ao R2."
    )


def push(nome: str, caminho=None) -> str:
    """Envia um config local para o R2. Retorna a chave escrita."""
    caminho = caminho or _local(nome)
    raw = open(caminho, "rb").read()
    yaml.safe_load(raw.decode("utf-8"))          # falha cedo se o YAML for invalido
    from storage.r2 import upload_bytes
    chave = _chave(nome)
    upload_bytes(raw, chave, content_type="text/yaml")
    log.info("config de %s enviado para r2://%s", nome, chave)
    return chave


def listar() -> list[str]:
    """Nomes dos clientes com config no R2."""
    if not USE_REMOTE_STORAGE:
        # glob nao garante ordem: NTFS devolve alfabetico, ext4 (o CI) nao
        return sorted(p.stem.removeprefix("client_") for p in LOCAL_DIR.glob("client_*.yaml"))
    from storage.r2 import get_client
    from src.config import R2_BUCKET
    c = get_client()
    r = c.list_objects_v2(Bucket=R2_BUCKET, Prefix=f"{PREFIXO}/")
    return sorted(o["Key"].rsplit("/", 1)[-1].removesuffix(".yaml")
                  for o in r.get("Contents", []))
