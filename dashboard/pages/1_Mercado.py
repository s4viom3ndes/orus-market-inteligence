import streamlit as st
import polars as pl
from lib.theme import setup
from lib.r2_reader import load_latest_market_snapshot, load_category_names, cat_name

setup("Mercado")
st.markdown("<h1 style='font-size:34px;margin-bottom:20px'>Mercado por Categoria</h1>", unsafe_allow_html=True)

df = load_latest_market_snapshot()
if df.is_empty():
    st.warning("Sem dados.")
    st.stop()

names = load_category_names()
cats_available = sorted(df["category_id"].unique().to_list())
cats_sorted = sorted(cats_available, key=lambda c: cat_name(c, names).lower())
cat_id = st.selectbox(
    "Categoria",
    cats_sorted,
    format_func=lambda c: f"{cat_name(c, names)} ({c})",
    label_visibility="collapsed",
)

sub = df.filter(pl.col("category_id") == cat_id)

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Ofertas", f"{sub.height:,}".replace(",", "."))
c2.metric("Produtos distintos", f"{sub['catalog_product_id'].n_unique():,}".replace(",", "."))
c3.metric("Vendedores", f"{sub['seller_id'].n_unique():,}".replace(",", "."))

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<h3 style='margin:0 0 14px'>Produtos mais competidos nessa categoria</h3>", unsafe_allow_html=True)

top = (sub.group_by(["catalog_product_id", "product_name"])
       .agg(
           pl.len().alias("n_sellers"),
           pl.col("price").min().alias("min_price"),
           pl.col("price").max().alias("max_price"),
           pl.col("price").mean().round(2).alias("avg_price"),
           pl.col("visits_30d").max().alias("visits_30d"),
       ).sort("n_sellers", descending=True).head(20))
st.dataframe(top, use_container_width=True, hide_index=True)

st.markdown("<h3 style='margin:24px 0 14px'>Ofertas nessa categoria</h3>", unsafe_allow_html=True)
st.dataframe(
    sub.sort(["catalog_product_id", "rank"]).select([
        "product_name", "seller_id", "price", "shipping_logistic_type",
        "shipping_free", "condition", "rank", "is_buy_box_winner",
        "visits_30d", "reviews_count", "reviews_avg_rating",
    ]),
    use_container_width=True, hide_index=True,
)
