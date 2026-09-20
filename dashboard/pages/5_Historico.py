"""Historico dia-a-dia do desempenho do cliente na Buy Box.

Le buy_box_history/date=*/*.parquet do R2 e plota:
- KPIs de cobertura (% dias ganhando, gap medio)
- Linha do tempo por SKU: posicao, preco, winner_price
- Tabela resumo por SKU
"""
import polars as pl
import streamlit as st
import altair as alt
from lib.theme import setup, ACCENT, DIVIDER, TEXT
from lib.components import tag, fmt_int
from lib.r2_reader import load_buy_box_history

setup("Histórico")

st.markdown(
    "<h1 style='font-size:34px;margin-bottom:6px'>Histórico dia-a-dia</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='font-size:15px;opacity:0.6;margin-bottom:24px'>"
    "Cada medição diária registra, para cada produto acompanhado, a sua posição, o seu "
    "preço e a distância até quem está com o destaque.</div>",
    unsafe_allow_html=True,
)

df = load_buy_box_history()

# O historico acumulou duas origens: linhas reais do vendedor e linhas de SKUs de
# demonstracao usados antes da carteira real entrar. Misturar as duas numa tela
# de cliente mostraria codigos de produto que nao sao dele - so a origem real
# entra aqui.
if not df.is_empty() and "source" in df.columns:
    df = df.filter(pl.col("source") == "real")

if df.is_empty():
    st.info(
        "O histórico começa a aparecer conforme as medições diárias se acumulam. "
        "Cada dia acrescenta um ponto à série de cada produto."
    )
    st.stop()

df = df.with_columns(
    pl.col("captured_date").str.strptime(pl.Date, "%Y-%m-%d", strict=False).alias("date")
).sort("date")

# ------------------------------- KPIs topo
n_days = df.select("date").n_unique()
n_skus = df.select("sku").n_unique()
n_snapshots = df.height
winning_rate = (df.filter(pl.col("is_buy_box_winner")).height / n_snapshots) if n_snapshots else 0
avg_gap = df.filter(~pl.col("is_buy_box_winner")).select(pl.col("gap_to_winner").mean()).item() or 0

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55'>Dias com dado</div>"
                f"<div style='font-size:28px;font-weight:800'>{n_days}</div>", unsafe_allow_html=True)
with k2:
    st.markdown(f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55'>SKUs acompanhados</div>"
                f"<div style='font-size:28px;font-weight:800'>{n_skus}</div>", unsafe_allow_html=True)
with k3:
    st.markdown(f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55'>% ganhando buy box</div>"
                f"<div style='font-size:28px;font-weight:800;color:{ACCENT}'>{winning_rate*100:.0f}%</div>", unsafe_allow_html=True)
with k4:
    st.markdown(f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55'>Gap médio quando perde</div>"
                f"<div style='font-size:28px;font-weight:800'>R$ {avg_gap:+.2f}</div>", unsafe_allow_html=True)

st.markdown(f"<hr style='border-top:1px solid {DIVIDER};margin:24px 0'>", unsafe_allow_html=True)

# ------------------------------- Seletor de SKU
sku_options = df.select("sku").unique().sort("sku")["sku"].to_list()
selected = st.selectbox("SKU", sku_options, label_visibility="collapsed")

sku_df = df.filter(pl.col("sku") == selected).sort("date")
if sku_df.is_empty():
    st.warning("Sem dados pra esse SKU.")
    st.stop()

first = sku_df.row(0, named=True)
last = sku_df.row(sku_df.height - 1, named=True)

st.markdown(
    f"<div style='margin:8px 0 20px'>"
    f"<div style='font-size:20px;font-weight:800'>{first['product_name']}</div>"
    f"<div style='font-size:12px;opacity:0.55;font-family:ui-monospace,monospace'>"
    f"catalog {first['catalog_product_id']} · fonte {first['source']}</div>"
    f"</div>",
    unsafe_allow_html=True,
)

# ------------------------------- Cards resumo do SKU
c1, c2, c3, c4 = st.columns(4)
days_won = int(sku_df.filter(pl.col("is_buy_box_winner")).height)
days_total = sku_df.height
last_status = "GANHANDO" if last["is_buy_box_winner"] else "PERDENDO"
last_style = "accent" if last["is_buy_box_winner"] else "outline"

with c1:
    st.markdown("<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55'>Status hoje</div>",
                unsafe_allow_html=True)
    st.markdown(tag(last_status, last_style, size_px=11), unsafe_allow_html=True)
with c2:
    st.markdown(f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55'>Dias na buy box</div>"
                f"<div style='font-size:22px;font-weight:800'>{days_won}/{days_total}</div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55'>Meu preço agora</div>"
                f"<div style='font-size:22px;font-weight:800'>R$ {last['current_price']:.2f}</div>", unsafe_allow_html=True)
with c4:
    st.markdown(f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:0.06em;opacity:0.55'>Winner atual</div>"
                f"<div style='font-size:22px;font-weight:800'>R$ {last['winner_price']:.2f}</div>", unsafe_allow_html=True)

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ------------------------------- Grafico 1: preço nosso vs winner ao longo do tempo
chart_df = sku_df.select(["date", "current_price", "winner_price"]).to_pandas()
chart_long = chart_df.melt(id_vars="date", var_name="serie", value_name="preco")
chart_long["serie"] = chart_long["serie"].map({"current_price": "Meu preço", "winner_price": "Winner"})

st.markdown("<h3 style='margin:0 0 12px;font-size:18px'>Preço vs Winner</h3>", unsafe_allow_html=True)
if len(chart_df) < 2:
    st.info("A tendência aparece a partir do segundo dia de medição deste produto.")
else:
    color_scale = alt.Scale(domain=["Meu preço", "Winner"], range=[ACCENT, TEXT])
    chart = (
        alt.Chart(chart_long)
        .mark_line(point=True, strokeWidth=3)
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("preco:Q", title="R$", scale=alt.Scale(zero=False)),
            color=alt.Color("serie:N", scale=color_scale, legend=alt.Legend(orient="top", title=None)),
            tooltip=["date:T", "serie:N", alt.Tooltip("preco:Q", format=".2f")],
        )
        .properties(height=280)
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False, labelFontSize=12, titleFontSize=11)
    )
    st.altair_chart(chart, use_container_width=True)

# ------------------------------- Grafico 2: posição no ranking
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.markdown("<h3 style='margin:0 0 12px;font-size:18px'>Posição no ranking</h3>", unsafe_allow_html=True)

pos_df = sku_df.select(["date", "our_position", "n_competitors"]).to_pandas()
if len(pos_df) < 2:
    st.info("A evolução aparece conforme mais dias forem medidos.")
else:
    pos_chart = (
        alt.Chart(pos_df)
        .mark_area(color=ACCENT, opacity=0.15, line={"color": ACCENT, "strokeWidth": 3})
        .encode(
            x=alt.X("date:T", title=None),
            y=alt.Y("our_position:Q", title="Posição (0 = buy box)",
                    scale=alt.Scale(reverse=True, zero=False)),
            tooltip=["date:T", "our_position:Q", "n_competitors:Q"],
        )
        .properties(height=200)
        .configure_view(strokeWidth=0)
        .configure_axis(grid=False, labelFontSize=12, titleFontSize=11)
    )
    st.altair_chart(pos_chart, use_container_width=True)

# ------------------------------- Tabela resumo por SKU
st.markdown(f"<hr style='border-top:1px solid {DIVIDER};margin:32px 0 16px'>", unsafe_allow_html=True)
st.markdown("<h3 style='margin:0 0 14px;font-size:18px'>Resumo por SKU</h3>", unsafe_allow_html=True)

summary = (
    df.group_by("sku")
    .agg([
        pl.col("product_name").first().alias("produto"),
        pl.col("date").n_unique().alias("dias"),
        pl.col("is_buy_box_winner").sum().alias("dias_ganhando"),
        pl.col("current_price").last().alias("preco_atual"),
        pl.col("winner_price").last().alias("winner_atual"),
        pl.col("gap_to_winner").mean().round(2).alias("gap_medio"),
    ])
    .with_columns(
        (pl.col("dias_ganhando") / pl.col("dias") * 100).round(0).cast(pl.Int64).alias("cobertura_%")
    )
    .sort("cobertura_%", descending=True)
    .select(["sku", "produto", "dias", "dias_ganhando", "cobertura_%",
             "preco_atual", "winner_atual", "gap_medio"])
)

st.dataframe(summary.to_pandas(), use_container_width=True, hide_index=True)

st.caption(f"Última atualização · {last['captured_date']} · {fmt_int(df.height)} pontos totais")
