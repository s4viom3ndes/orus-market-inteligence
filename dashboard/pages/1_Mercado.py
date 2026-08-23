import streamlit as st
import polars as pl
from lib.r2_reader import load_latest_market_snapshot

st.set_page_config(page_title="Mercado por categoria", page_icon="📈", layout="wide")
st.title("📈 Mercado por Categoria")

df = load_latest_market_snapshot()
if df.is_empty():
    st.warning("Sem dados.")
    st.stop()

cats = sorted(df["category_id"].unique().to_list())
cat_id = st.selectbox("Categoria", cats)

sub = df.filter(pl.col("category_id") == cat_id)

col1, col2, col3 = st.columns(3)
col1.metric("Ofertas", sub.height)
col2.metric("Produtos distintos", sub["catalog_product_id"].n_unique())
col3.metric("Vendedores", sub["seller_id"].n_unique())

st.subheader("Produtos mais competidos nessa categoria")
top = (sub.group_by(["catalog_product_id", "product_name"])
       .agg(
           pl.len().alias("n_sellers"),
           pl.col("price").min().alias("min_price"),
           pl.col("price").max().alias("max_price"),
           pl.col("price").mean().round(2).alias("avg_price"),
           pl.col("visits_30d").max().alias("visits_30d"),
       ).sort("n_sellers", descending=True).head(20))
st.dataframe(top, use_container_width=True, hide_index=True)

st.subheader("Ofertas nessa categoria")
st.dataframe(
    sub.select([
        "catalog_product_id", "product_name", "seller_id", "price",
        "shipping_logistic_type", "shipping_free", "condition", "rank",
        "is_buy_box_winner", "visits_30d", "reviews_count", "reviews_avg_rating"
    ]).sort(["catalog_product_id", "rank"]),
    use_container_width=True, hide_index=True
)
