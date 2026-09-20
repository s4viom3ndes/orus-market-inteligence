import streamlit as st
import polars as pl
from lib.theme import setup
from lib.r2_reader import load_latest_market_snapshot, load_category_names, cat_name

setup("Mercado")
st.markdown("<h1 style='font-size:34px;margin-bottom:6px'>Mercado por categoria</h1>",
            unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:15px;opacity:0.65;margin-bottom:22px;max-width:760px;line-height:1.6'>"
    "Escolha uma categoria para ver quem está vendendo ali, a que preço, e quais produtos "
    "concentram a disputa.</div>",
    unsafe_allow_html=True,
)

df = load_latest_market_snapshot()
if df.is_empty():
    st.info("Os dados de mercado ainda não foram coletados.")
    st.stop()

names = load_category_names()
cats_available = sorted(df["category_id"].unique().to_list())
cats_sorted = sorted(cats_available, key=lambda c: cat_name(c, names).lower())
cat_id = st.selectbox(
    "Categoria",
    cats_sorted,
    format_func=lambda c: cat_name(c, names),
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

# O codigo interno do produto nao diz nada a quem le - so o nome fica.
top = (sub.group_by(["catalog_product_id", "product_name"])
       .agg(
           pl.len().alias("Vendedores"),
           pl.col("price").min().alias("Menor preço"),
           pl.col("price").max().alias("Maior preço"),
           pl.col("price").mean().round(2).alias("Preço médio"),
           pl.col("visits_30d").max().alias("Visitas (30d)"),
       ).sort("Vendedores", descending=True).head(20)
       .select([pl.col("product_name").alias("Produto"), "Vendedores",
                "Menor preço", "Maior preço", "Preço médio", "Visitas (30d)"]))
st.dataframe(top, use_container_width=True, hide_index=True)

st.markdown("<h3 style='margin:24px 0 14px'>Ofertas nessa categoria</h3>", unsafe_allow_html=True)
st.dataframe(
    sub.sort(["catalog_product_id", "rank"]).select([
        pl.col("product_name").alias("Produto"),
        (pl.col("rank") + 1).alias("Posição"),
        pl.col("price").alias("Preço"),
        pl.col("shipping_logistic_type").alias("Logística"),
        pl.col("shipping_free").alias("Frete grátis"),
        pl.col("condition").alias("Condição"),
        pl.col("visits_30d").alias("Visitas (30d)"),
        pl.col("reviews_count").alias("Avaliações"),
        pl.col("reviews_avg_rating").alias("Nota"),
    ]),
    use_container_width=True, hide_index=True,
)
