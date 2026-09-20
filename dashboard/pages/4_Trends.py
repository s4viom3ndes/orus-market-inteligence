"""O que o Brasil esta buscando no Mercado Livre, e como isso se move.

A API de tendencias devolve o termo e a posicao dele - nao devolve visitas nem
preco por termo. Entao o que esta tela mostra nao e "quanto vale cada busca", e
sim o MOVIMENTO: acompanhando dia a dia, aparece o que subiu, o que caiu e o que
acabou de entrar na lista. Isso a foto de um dia nao conta.
"""
import datetime

import altair as alt
import polars as pl
import streamlit as st

from lib.theme import setup, ACCENT, TEXT, NEUTRAL_200
from lib.components import page_header
from lib.r2_reader import load_latest_trends, load_trends_history

setup("Trends")

page_header(
    "O que o Brasil está buscando",
    "As buscas em alta do Mercado Livre, medidas todos os dias. O interessante não é a "
    "lista de hoje — é ver um termo subindo antes de ele virar concorrência.",
)

df = load_latest_trends()
if df.is_empty():
    st.info("Ainda sem dados de tendências.")
    st.stop()

captured = int(df["captured_at"].max())
quando = datetime.datetime.fromtimestamp(captured).strftime("%d/%m/%Y às %H:%M")

hist = load_trends_history(dias=8)
site_hist = hist.filter(pl.col("scope") == "site") if not hist.is_empty() else pl.DataFrame()

# ------------------------------------------------------------- quem se moveu
if not site_hist.is_empty() and site_hist["dia"].n_unique() >= 2:
    dias = sorted(site_hist["dia"].unique().to_list())
    hoje, antes = dias[-1], dias[0]

    r_hoje = (site_hist.filter(pl.col("dia") == hoje)
              .select(["keyword", pl.col("rank").alias("hoje")]))
    r_antes = (site_hist.filter(pl.col("dia") == antes)
               .select(["keyword", pl.col("rank").alias("antes")]))
    mov = r_hoje.join(r_antes, on="keyword", how="left")

    novos = mov.filter(pl.col("antes").is_null())
    movidos = (mov.drop_nulls("antes")
               .with_columns((pl.col("antes") - pl.col("hoje")).alias("ganho")))
    subiram = movidos.filter(pl.col("ganho") > 0).sort("ganho", descending=True)
    cairam = movidos.filter(pl.col("ganho") < 0).sort("ganho")

    st.markdown("### O que mudou nos últimos dias")
    st.markdown(
        f"<div style='font-size:14px;opacity:.7;margin-bottom:16px'>"
        f"Comparando {antes.split('-')[2]}/{antes.split('-')[1]} com "
        f"{hoje.split('-')[2]}/{hoje.split('-')[1]}.</div>",
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    for col, dados, titulo, cor in (
        (c1, subiram.head(6), "Subiram", ACCENT),
        (c2, cairam.head(6), "Caíram", TEXT),
        (c3, novos.head(6), "Entraram agora", ACCENT),
    ):
        with col:
            col.markdown(
                f"<div style='font-size:11px;text-transform:uppercase;letter-spacing:.06em;"
                f"opacity:.55;margin-bottom:8px'>{titulo}</div>",
                unsafe_allow_html=True,
            )
            if dados.is_empty():
                col.markdown("<div style='font-size:13px;opacity:.5'>—</div>",
                             unsafe_allow_html=True)
                continue
            for r in dados.iter_rows(named=True):
                if "ganho" in r and r.get("ganho") is not None:
                    n = int(r["ganho"])
                    marca = f"{'▲' if n > 0 else '▼'} {abs(n)}"
                else:
                    marca = "novo"
                col.markdown(
                    f"<div style='display:flex;justify-content:space-between;gap:10px;"
                    f"padding:6px 0;border-bottom:1px solid {NEUTRAL_200};font-size:13.5px'>"
                    f"<span>{r['keyword']}</span>"
                    f"<span style='color:{cor};font-weight:800;white-space:nowrap'>{marca}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ---------------------------------------------------------------- grafico
    st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:26px 0 16px'>",
                unsafe_allow_html=True)
    st.markdown("### Trajetória dos termos mais buscados")

    topo = (site_hist.filter(pl.col("dia") == hoje).sort("rank").head(8)["keyword"].to_list())
    serie = site_hist.filter(pl.col("keyword").is_in(topo)).select(["dia", "keyword", "rank"])
    # rank 0 é a primeira posição; somar 1 deixa o eixo legível para quem lê
    serie = serie.with_columns((pl.col("rank") + 1).alias("posicao"))

    linha = alt.Chart(serie.to_pandas()).mark_line(point=True, strokeWidth=2).encode(
        x=alt.X("dia:N", title=""),
        # escala invertida: posição 1 no alto, que é como as pessoas leem ranking
        y=alt.Y("posicao:Q", title="posição na lista",
                scale=alt.Scale(reverse=True, zero=False)),
        color=alt.Color("keyword:N", title="", legend=alt.Legend(orient="right")),
        tooltip=["dia", "keyword", "posicao"],
    ).properties(height=320)
    st.altair_chart(linha, use_container_width=True)
    st.caption(
        "Quanto mais alto no gráfico, mais buscado. Uma linha que sobe é um produto "
        "ganhando procura — e, normalmente, ganhando concorrente logo em seguida."
    )

st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:26px 0 16px'>",
            unsafe_allow_html=True)

# --------------------------------------------------------------- lista de hoje
st.markdown("### As 25 buscas mais fortes de hoje")
site = df.filter(pl.col("scope") == "site").sort("rank").head(25)
st.dataframe(
    site.select([
        (pl.col("rank") + 1).alias("Posição"),
        pl.col("keyword").alias("O que estão buscando"),
    ]).to_pandas(),
    use_container_width=True, hide_index=True,
)
st.caption(f"Medido em {quando}. A lista é do Mercado Livre e vale para o Brasil inteiro, "
           "não só para as suas categorias.")
