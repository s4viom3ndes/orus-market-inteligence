import streamlit as st
import polars as pl
from lib.r2_reader import load_latest_trends, list_snapshots, read_parquet

st.set_page_config(page_title="Trends", page_icon="🔥", layout="wide")
st.title("🔥 Trending Searches - Mercado Livre BR")

df = load_latest_trends()
if df.is_empty():
    st.warning("Nenhum snapshot de trends.")
    st.stop()

captured = df["captured_at"].max()
import datetime
st.caption(f"Snapshot capturado em: {datetime.datetime.fromtimestamp(captured)}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Top 25 do site (Brasil)")
    site = df.filter(pl.col("scope") == "site").sort("rank").head(25)
    st.dataframe(site.select(["rank", "keyword", "url"]), use_container_width=True, hide_index=True)

with col2:
    st.subheader("Trends por categoria (se disponivel)")
    cats = df.filter(pl.col("scope") == "category")
    if cats.is_empty():
        st.info("ML nao expoe trends por categoria pras raizes atuais.")
    else:
        st.dataframe(cats.select(["category_id", "rank", "keyword"]), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Historico de snapshots (ultimos 30)")
snaps = list_snapshots("trends/")
snaps_sorted = sorted(snaps, key=lambda x: x["last_modified"], reverse=True)[:30]
st.dataframe(
    pl.DataFrame([{
        "when": s["last_modified"].strftime("%Y-%m-%d %H:%M"),
        "key": s["key"],
        "size_kb": round(s["size"]/1024, 1),
    } for s in snaps_sorted]),
    use_container_width=True, hide_index=True
)
