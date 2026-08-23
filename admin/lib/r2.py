import io
import json
import os
from pathlib import Path
import boto3
from botocore.client import Config
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


@st.cache_data(ttl=60)
def list_objects(prefix: str) -> list[dict]:
    c = get_client()
    r = c.list_objects_v2(Bucket=R2_BUCKET, Prefix=prefix)
    return [
        {"key": o["Key"], "size": o["Size"], "last_modified": o["LastModified"]}
        for o in r.get("Contents", [])
    ]


@st.cache_data(ttl=60)
def get_json(key: str) -> dict:
    c = get_client()
    obj = c.get_object(Bucket=R2_BUCKET, Key=key)
    return json.loads(obj["Body"].read())


@st.cache_data(ttl=60)
def read_parquet(key: str):
    import polars as pl
    c = get_client()
    obj = c.get_object(Bucket=R2_BUCKET, Key=key)
    return pl.read_parquet(io.BytesIO(obj["Body"].read()))
