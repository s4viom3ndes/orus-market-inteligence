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
    st.info("Ainda sem dados de tendências.")
    st.stop()

captured = int(df["captured_at"].max())
st.markdown(
    f"<div style='font-size:15px;opacity:0.6;margin-bottom:28px'>Medido em: {datetime.datetime.fromtimestamp(captured)}</div>",
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
st.markdown("<h3 style='margin:24px 0 14px'>Medições recentes</h3>", unsafe_allow_html=True)

# A tabela antiga listava caminho de arquivo e tamanho em KB - informacao de
# operacao, nao de negocio. O que interessa ao leitor e desde quando isto e
# medido e com que regularidade.
snaps = sorted(list_snapshots("trends/"), key=lambda x: x["last_modified"], reverse=True)[:30]
if snaps:
    dias = sorted({s["last_modified"].strftime("%d/%m") for s in snaps})
    st.markdown(
        f"<div style='font-size:14px;line-height:1.6'>As buscas em alta são medidas todos os "
        f"dias. As {len(dias)} medições mais recentes vão de <b>{dias[0]}</b> a "
        f"<b>{dias[-1]}</b>.</div>",
        unsafe_allow_html=True,
    )
