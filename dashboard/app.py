import streamlit as st
import polars as pl
from lib.r2_reader import load_latest_market_snapshot, load_all_market_snapshots, load_latest_trends

st.set_page_config(page_title="Orus - Market Intelligence", page_icon="🎯", layout="wide")

st.title("🎯 Orus - Market Intelligence")
st.caption("Coleta e analisa o mercado do Mercado Livre. Buy Box, competicao, precos e tendencias.")

with st.spinner("Carregando snapshot mais recente..."):
    df = load_latest_market_snapshot()

if df.is_empty():
    st.warning("Nenhum snapshot encontrado no R2 ainda. Rode `python -m jobs.collect_market` primeiro.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ofertas coletadas", f"{df.height:,}")
col2.metric("Produtos de catalogo", df["catalog_product_id"].n_unique())
col3.metric("Vendedores unicos", df["seller_id"].n_unique())
col4.metric("Categorias", df["category_id"].n_unique())

st.divider()

st.subheader("Distribuicao por categoria")
by_cat = (df.group_by("category_id").agg(
    pl.len().alias("ofertas"),
    pl.col("catalog_product_id").n_unique().alias("produtos"),
    pl.col("seller_id").n_unique().alias("vendedores"),
    pl.col("price").mean().round(2).alias("preco_medio"),
).sort("ofertas", descending=True))
st.dataframe(by_cat, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Buy Box winners (esse snapshot)")
winners = df.filter(pl.col("is_buy_box_winner")).select(
    ["product_name", "seller_id", "price", "shipping_logistic_type", "visits_30d", "reviews_count"]
).sort("visits_30d", descending=True, nulls_last=True).head(20)
st.dataframe(winners, use_container_width=True, hide_index=True)

st.divider()

col_a, col_b = st.columns(2)
with col_a:
    st.subheader("Insight: logistica dos winners")
    shipping = (df.filter(pl.col("is_buy_box_winner"))
                .group_by("shipping_logistic_type")
                .agg(pl.len().alias("winners"))
                .sort("winners", descending=True))
    st.bar_chart(shipping.to_pandas().set_index("shipping_logistic_type"))

with col_b:
    st.subheader("Trending searches no ML BR agora")
    trends = load_latest_trends()
    if not trends.is_empty():
        top = trends.filter(pl.col("scope") == "site").head(15)
        st.dataframe(top.select(["rank", "keyword"]), use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum snapshot de trends ainda.")

st.divider()
st.caption("Use o menu esquerdo pra navegar entre paginas.")
