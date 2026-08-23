import datetime
import streamlit as st
import polars as pl
from lib.theme import setup
from lib.r2_reader import load_latest_trends, list_snapshots

setup("Trends")

st.markdown("<h1 style='font-size:34px;margin-bottom:6px'>Trending Searches — Mercado Livre BR</h1>",
            unsafe_allow_html=True)

df = load_latest_trends()
if df.is_empty():
    st.warning("Nenhum snapshot de trends.")
    st.stop()

captured = int(df["captured_at"].max())
st.markdown(
    f"<div style='font-size:15px;opacity:0.6;margin-bottom:28px'>Snapshot: {datetime.datetime.fromtimestamp(captured)}</div>",
    unsafe_allow_html=True,
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("<h3 style='margin:0 0 14px'>Top 25 do site (Brasil)</h3>", unsafe_allow_html=True)
    site = df.filter(pl.col("scope") == "site").sort("rank").head(25)
    st.dataframe(site.select(["rank", "keyword", "url"]), use_container_width=True, hide_index=True)

with col2:
    st.markdown("<h3 style='margin:0 0 14px'>Trends por categoria</h3>", unsafe_allow_html=True)
    cats = df.filter(pl.col("scope") == "category")
    if cats.is_empty():
        st.info("ML não expõe trends por categoria pras raízes atuais.")
    else:
        st.dataframe(cats.select(["category_id", "rank", "keyword"]),
                     use_container_width=True, hide_index=True)

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<h3 style='margin:24px 0 14px'>Histórico de snapshots (últimos 30)</h3>", unsafe_allow_html=True)

snaps = sorted(list_snapshots("trends/"), key=lambda x: x["last_modified"], reverse=True)[:30]
st.dataframe(
    pl.DataFrame([{
        "when": s["last_modified"].strftime("%Y-%m-%d %H:%M"),
        "key": s["key"],
        "size_kb": round(s["size"] / 1024, 1),
    } for s in snaps]),
    use_container_width=True, hide_index=True,
)
