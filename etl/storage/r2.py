import logging
from pathlib import Path
from typing import Optional
import boto3
from botocore.client import Config
from src.config import (
    R2_ENDPOINT,
    R2_ACCESS_KEY_ID,
    R2_SECRET_ACCESS_KEY,
    R2_BUCKET,
    USE_REMOTE_STORAGE,
)

log = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        if not USE_REMOTE_STORAGE:
            raise RuntimeError("R2 nao configurado (falta R2_ENDPOINT/R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY)")
        _client = boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _client


def upload_file(local_path: Path, key: str) -> str:
    get_client().upload_file(str(local_path), R2_BUCKET, key)
    log.info("upload OK: r2://%s/%s (%s bytes)", R2_BUCKET, key, local_path.stat().st_size)
    return f"r2://{R2_BUCKET}/{key}"


def upload_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    get_client().put_object(Bucket=R2_BUCKET, Key=key, Body=data, ContentType=content_type)
    log.info("upload OK: r2://%s/%s (%s bytes)", R2_BUCKET, key, len(data))
    return f"r2://{R2_BUCKET}/{key}"


def download_bytes(key: str) -> Optional[bytes]:
    try:
        obj = get_client().get_object(Bucket=R2_BUCKET, Key=key)
        return obj["Body"].read()
    except get_client().exceptions.NoSuchKey:
        return None


def list_keys(prefix: str) -> list[dict]:
    """Todas as chaves sob o prefixo, paginando.

    `list_objects_v2` devolve no maximo 1000 por chamada. Quem nao pagina nao
    recebe um erro - recebe um recorte silencioso, e em ordem lexicografica,
    entao o recorte fica justamente com as chaves mais ANTIGAS.
    """
    paginator = get_client().get_paginator("list_objects_v2")
    saida: list[dict] = []
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix):
        saida.extend(
            {"key": o["Key"], "size": o["Size"], "last_modified": o["LastModified"]}
            for o in page.get("Contents", [])
        )
    return saida


def latest_key(dataset: str) -> Optional[str]:
    """Chave do snapshot mais recente de um dataset.

    Le o ponteiro `state/latest/{dataset}.json` que `parquet_writer` grava a cada
    escrita. Se o ponteiro nao existir (datasets escritos antes dele), cai para a
    varredura paginada - correta, so mais cara.
    """
    import json
    raw = download_bytes(f"state/latest/{dataset}.json")
    if raw:
        try:
            return json.loads(raw)["key"]
        except (ValueError, KeyError) as e:
            log.warning("ponteiro de %s ilegivel (%s), varrendo o prefixo", dataset, e)

    objs = list_keys(f"{dataset}/")
    if not objs:
        return None
    return max(objs, key=lambda o: o["last_modified"])["key"]
