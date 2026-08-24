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
    c = get_client()
    r = c.list_objects_v2(Bucket=R2_BUCKET, Prefix=prefix)
    return [
        {"key": o["Key"], "size": o["Size"], "last_modified": o["LastModified"]}
        for o in r.get("Contents", [])
    ]


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
    snaps = list_snapshots("market_offers/")
    if not snaps:
        return pl.DataFrame()
    latest = max(snaps, key=lambda x: x["last_modified"])
    return read_parquet(latest["key"])


@st.cache_data(ttl=600)
def load_latest_trends() -> pl.DataFrame:
    snaps = list_snapshots("trends/")
    if not snaps:
        return pl.DataFrame()
    latest = max(snaps, key=lambda x: x["last_modified"])
    return read_parquet(latest["key"])


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
