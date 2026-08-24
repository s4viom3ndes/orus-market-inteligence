import streamlit as st
import polars as pl
from lib.theme import setup, ACCENT
from lib.components import bar_list_header, bar_list_row, horizontal_percent_bar, tag
from lib.r2_reader import load_latest_market_snapshot, load_latest_trends, load_category_names, cat_name

setup("Visão Geral")

st.markdown("<h1 style='font-size:34px;margin-bottom:6px'>Visão Geral</h1>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:15px;opacity:0.6;margin-bottom:32px'>Coleta e analisa o mercado do Mercado Livre. "
    "Buy Box, competição, preços e tendências.</div>",
    unsafe_allow_html=True,
)

with st.spinner("Carregando snapshot mais recente..."):
    df = load_latest_market_snapshot()

if df.is_empty():
    st.warning("Nenhum snapshot no R2 ainda.")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Ofertas coletadas", f"{df.height:,}".replace(",", "."))
c2.metric("Produtos de catálogo", f"{df['catalog_product_id'].n_unique():,}".replace(",", "."))
c3.metric("Vendedores únicos", f"{df['seller_id'].n_unique():,}".replace(",", "."))
c4.metric("Categorias", df["category_id"].n_unique())

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<h3 style='margin:24px 0 14px'>Distribuição por categoria</h3>", unsafe_allow_html=True)

by_cat = (df.group_by("category_id").agg(
    pl.len().alias("ofertas"),
    pl.col("catalog_product_id").n_unique().alias("produtos"),
    pl.col("seller_id").n_unique().alias("vendedores"),
    pl.col("price").mean().round(2).alias("preco_medio"),
).sort("ofertas", descending=True))

names = load_category_names()
bar_list_header("Categoria", "Ofertas", "Produtos · Vend. · Preço médio")

max_cat = by_cat["ofertas"].max()
for r in by_cat.head(15).rows(named=True):
    meta = f'{r["produtos"]} · {r["vendedores"]} · R$ {r["preco_medio"]:.2f}'
    bar_list_row(cat_name(r["category_id"], names), r["ofertas"], max_cat, meta,
                 sublabel=r["category_id"])

if by_cat.height > 15:
    st.markdown(
        f'<div style="padding:10px 0;font-size:12.5px;opacity:0.4">+ {by_cat.height - 15} categorias no snapshot completo</div>',
        unsafe_allow_html=True,
    )

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<h3 style='margin:24px 0 14px'>Buy Box winners (esse snapshot)</h3>", unsafe_allow_html=True)

winners = df.filter(pl.col("is_buy_box_winner")).sort("visits_30d", descending=True, nulls_last=True).head(20)

if not winners.is_empty():
    max_visits = winners.filter(pl.col("visits_30d").is_not_null())["visits_30d"].max() or 1
    bar_list_header("Produto", "Visitas 30d", "Preço · Aval.")
    for r in winners.rows(named=True):
        visits = r.get("visits_30d") or 0
        logistic = r.get("shipping_logistic_type") or "?"
        tag_style = "neutral" if logistic == "fulfillment" else "outline"
        seller = r.get("seller_id")
        reviews = r.get("reviews_count") or 0
        meta = f'R$ {r["price"]:,.2f} · {reviews:,.0f} aval.'.replace(",", ".")
        bar_list_row(
            (r.get("product_name") or "?")[:60],
            visits, max_visits, meta,
            sublabel=f"seller {seller}",
            tag_html=tag(logistic, tag_style),
        )

st.markdown("<hr>", unsafe_allow_html=True)

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("<h3 style='margin:0 0 14px'>Insight: logística dos winners</h3>", unsafe_allow_html=True)
    shipping = (df.filter(pl.col("is_buy_box_winner"))
                .group_by("shipping_logistic_type")
                .agg(pl.len().alias("n"))
                .sort("n", descending=True))
    total = shipping["n"].sum() or 1
    for r in shipping.rows(named=True):
        pct = (r["n"] / total) * 100
        horizontal_percent_bar(r["shipping_logistic_type"] or "?", pct)

with col_b:
    st.markdown("<h3 style='margin:0 0 14px'>Trending searches no ML BR agora</h3>", unsafe_allow_html=True)
    trends = load_latest_trends()
    if not trends.is_empty():
        top = trends.filter(pl.col("scope") == "site").sort("rank").head(12)
        st.dataframe(
            top.select(["rank", "keyword"]).rename({"rank": "rank", "keyword": "keyword"}),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Nenhum snapshot de trends.")
