import io
import os
from functools import lru_cache
from pathlib import Path
import boto3
from botocore.client import Config
import polars as pl
import streamlit as st

try:
    st.secrets["R2_ENDPOINT"]
    R2_ENDPOINT = st.secrets["R2_ENDPOINT"]
    R2_ACCESS_KEY_ID = st.secrets["R2_ACCESS_KEY_ID"]
    R2_SECRET_ACCESS_KEY = st.secrets["R2_SECRET_ACCESS_KEY"]
    R2_BUCKET = st.secrets["R2_BUCKET"]
except (FileNotFoundError, KeyError):
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / ".env")
    R2_ENDPOINT = os.getenv("R2_ENDPOINT", "")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET = os.getenv("R2_BUCKET", "orus-github-actions")


@st.cache_resource
def get_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


@st.cache_data(ttl=600)
def list_snapshots(prefix: str) -> list[dict]:
    """Chaves sob o prefixo, paginando.

    `list_objects_v2` devolve no maximo 1000 por chamada, em ordem lexicografica.
    Sem paginar, ao passar desse volume a lista fica so com as chaves mais
    ANTIGAS - e quem pega o max por last_modified acaba servindo dado velho sem
    erro nenhum.
    """
    paginator = get_client().get_paginator("list_objects_v2")
    saida: list[dict] = []
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix):
        saida.extend(
            {"key": o["Key"], "size": o["Size"], "last_modified": o["LastModified"]}
            for o in page.get("Contents", [])
        )
    return saida


@st.cache_data(ttl=600)
def latest_key(dataset: str) -> str | None:
    """Chave do snapshot mais recente, via ponteiro state/latest/{dataset}.json.

    O ponteiro e escrito por etl/storage/parquet_writer a cada snapshot. Datasets
    escritos antes dele caem na varredura paginada.
    """
    import json
    try:
        obj = get_client().get_object(Bucket=R2_BUCKET, Key=f"state/latest/{dataset}.json")
        return json.loads(obj["Body"].read())["key"]
    except Exception:
        pass
    snaps = list_snapshots(f"{dataset}/")
    return max(snaps, key=lambda x: x["last_modified"])["key"] if snaps else None


def load_latest(dataset: str) -> pl.DataFrame:
    key = latest_key(dataset)
    return read_parquet(key) if key else pl.DataFrame()


@st.cache_data(ttl=600)
def read_parquet(key: str) -> pl.DataFrame:
    c = get_client()
    obj = c.get_object(Bucket=R2_BUCKET, Key=key)
    return pl.read_parquet(io.BytesIO(obj["Body"].read()))


@st.cache_data(ttl=600)
def load_all_market_snapshots() -> pl.DataFrame:
    snaps = list_snapshots("market_offers/")
    if not snaps:
        return pl.DataFrame()
    dfs = [read_parquet(s["key"]) for s in snaps]
    return pl.concat(dfs, how="diagonal_relaxed")


@st.cache_data(ttl=600)
def load_latest_market_snapshot() -> pl.DataFrame:
    return load_latest("market_offers")


@st.cache_data(ttl=600)
def load_latest_trends() -> pl.DataFrame:
    return load_latest("trends")


@st.cache_data(ttl=600)
def load_market_history(dias: int = 7, produtos: tuple[str, ...] = ()) -> pl.DataFrame:
    """Ultimos N snapshots de mercado, opcionalmente so de alguns produtos.

    `load_all_market_snapshots` existe mas traz o painel inteiro (~15 MB hoje, e
    crescendo todo dia). Para acompanhar um punhado de catalogos ao longo de uma
    semana isso e desperdicio: aqui filtra-se por produto ja na leitura de cada
    arquivo, entao o que fica em memoria e so o recorte que a tela usa.
    """
    snaps = list_snapshots("market_offers/")
    if not snaps:
        return pl.DataFrame()
    recentes = sorted(snaps, key=lambda x: x["last_modified"])[-dias:]
    partes = []
    for s in recentes:
        df = read_parquet(s["key"])
        if df.is_empty():
            continue
        if produtos:
            df = df.filter(pl.col("catalog_product_id").is_in(list(produtos)))
        if not df.is_empty():
            # a data vem da chave: captured_at e epoch e o parquet nao traz o dia
            dia = s["key"].split("date=")[1][:10] if "date=" in s["key"] else ""
            partes.append(df.with_columns(pl.lit(dia).alias("dia")))
    return pl.concat(partes, how="diagonal_relaxed") if partes else pl.DataFrame()


def sem_precos_absurdos(df: pl.DataFrame, fator: float = 20.0) -> pl.DataFrame:
    """Descarta ofertas com preco acima de `fator` x a mediana do proprio produto.

    ~0,03% das ofertas do ML tem preco de digitacao errada (um item de R$27 com
    concorrente a R$399.900.000). Nunca vencem nada, mas arruinam qualquer
    estatistica de "menor preco" ou "mediana do catalogo".

    Mesma regra de services/market_insights.remove_price_outliers no ETL. Esta
    copia existe porque o dashboard nao importa de etl/ - se um dia a regra
    mudar, os dois lados precisam mudar juntos.
    """
    if df.is_empty() or "price" not in df.columns:
        return df
    return (
        df.with_columns(pl.col("price").median().over("catalog_product_id").alias("_med"))
        .filter(pl.col("price") <= pl.col("_med") * fator)
        .drop("_med")
    )


@st.cache_data(ttl=600)
def load_latest_optimizer() -> pl.DataFrame:
    """Preco otimo por SKU (services/price_optimizer, job optimize_prices)."""
    return load_latest("price_optimizer")


@st.cache_data(ttl=600)
def load_latest_suggestions() -> pl.DataFrame:
    """Sugestoes do repricer v1 (regras). Motor antigo, mantido em paralelo."""
    return load_latest("reprice_suggestions")


# Qual cliente este dashboard serve. Vem de secret/env porque o repo e publico e
# o nome do cliente ja e informacao comercial.
CLIENT_SLUG = ""
try:
    CLIENT_SLUG = st.secrets.get("ORUS_CLIENT", "")
except (FileNotFoundError, AttributeError):
    pass
CLIENT_SLUG = CLIENT_SLUG or os.getenv("ORUS_CLIENT", "")


@st.cache_data(ttl=300)
def load_client_config() -> dict:
    """Config do cliente: state/clients/{slug}.yaml, caindo pro mock.

    Antes isto vivia copiado dentro de 2_Buy_Box.py e 3_Repricer.py, lendo so o
    mock. Centralizar aqui e o que permite a mesma tela servir um cliente real.

    A config devolvida carrega `_origem`: "cliente" ou "demonstracao". Sem isso o
    fallback era silencioso - se a variavel ORUS_CLIENT nao estivesse definida no
    ambiente (o caso tipico de um deploy novo, onde o .env nao existe), a tela
    servia SKUs ficticios sem nada indicando isso.
    """
    import yaml
    if CLIENT_SLUG:
        try:
            obj = get_client().get_object(Bucket=R2_BUCKET,
                                          Key=f"state/clients/{CLIENT_SLUG}.yaml")
            cfg = yaml.safe_load(obj["Body"].read()) or {}
            cfg["_origem"] = "cliente"
            return cfg
        except Exception:
            pass
    try:
        obj = get_client().get_object(Bucket=R2_BUCKET, Key="state/mock_client.yaml")
        cfg = yaml.safe_load(obj["Body"].read()) or {}
    except Exception:
        local = Path(__file__).parent.parent.parent / "etl" / "config" / "mock_client.yaml"
        cfg = yaml.safe_load(local.read_text(encoding="utf-8")) if local.exists() else {}
    cfg["_origem"] = "demonstracao"
    return cfg


def config_e_demonstracao(cfg: dict) -> bool:
    return (cfg or {}).get("_origem") != "cliente"


def seller_do_config(cfg: dict) -> tuple[str, str | int]:
    """(nome, seller_id) para o rodape da sidebar. Sem cair no mock hardcoded."""
    s = (cfg or {}).get("seller") or {}
    return s.get("name") or "—", s.get("ml_seller_id") or "—"


@st.cache_data(ttl=600)
def load_buy_box_state() -> dict:
    import json
    try:
        c = get_client()
        obj = c.get_object(Bucket=R2_BUCKET, Key="state/buy_box_state.json")
        return json.loads(obj["Body"].read())
    except Exception:
        return {}


@st.cache_data(ttl=600)
def load_buy_box_history() -> pl.DataFrame:
    """Concatena todos os snapshots de buy_box_history/date=*."""
    snaps = list_snapshots("buy_box_history/")
    if not snaps:
        return pl.DataFrame()
    dfs = [read_parquet(s["key"]) for s in snaps]
    return pl.concat(dfs, how="diagonal_relaxed")


@st.cache_data(ttl=600)
def load_category_names() -> dict:
    """Retorna {cat_id: {name, path}} do R2. Fallback pra dict vazio."""
    import json
    try:
        c = get_client()
        obj = c.get_object(Bucket=R2_BUCKET, Key="state/category_names.json")
        return json.loads(obj["Body"].read())
    except Exception:
        return {}


def cat_name(cat_id: str, cache: dict) -> str:
    entry = cache.get(cat_id)
    return entry.get("name") if entry else cat_id
