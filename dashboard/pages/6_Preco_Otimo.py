"""Preco que maximiza lucro esperado, por SKU.

Le price_optimizer/ do R2 - o resultado de services/price_optimizer, que escolhe
o preco por argmax de P(buy box) x margem, e nao por perseguir a buy box.

Ate esta tela existir, esse resultado so saia por email: o email consegue mostrar
a tabela, mas nao a curva, que e onde se ve POR QUE aquele preco e o otimo.
"""
import math

import altair as alt
import polars as pl
import streamlit as st

from lib.theme import setup, ACCENT, TEXT, NEUTRAL_200
from lib.components import (empty_state, fmt_brl, fmt_pct, kpi_row, page_header, tag)
from lib.r2_reader import load_client_config, load_latest_optimizer, seller_do_config

cfg = load_client_config()
setup("Preço Ótimo", *seller_do_config(cfg))

page_header(
    "Preço ótimo por SKU",
    "O preço recomendado maximiza P(buy box) × margem — não a chance de ganhar. "
    "Ganhar a buy box é fácil: basta cobrar pouco.",
)

df = load_latest_optimizer()
if df.is_empty():
    empty_state(
        "Ainda não há cálculo de preço",
        "Assim que a primeira rodada de otimização rodar sobre a sua carteira, "
        "a recomendação por SKU aparece aqui.",
    )
    st.stop()

# rotulo e se o status pede acao. Espelha services/price_optimizer.STATUS, que e
# a fonte de verdade do lado do ETL.
STATUS_UI = {
    "suggest_change":   ("Ajustar preço", "accent"),
    "hold":             ("Já está no ótimo", "neutral"),
    "locked":           ("Travado", "outline"),
    "inviavel":         ("Não fecha", "outline"),
    "sem_custo":        ("Falta custo", "outline"),
    "sem_concorrencia": ("Sem disputa", "neutral"),
    "sem_mercado":      ("Sem ofertas", "neutral"),
    "no_data":          ("Sem dado", "neutral"),
}


def _status(s: str) -> tuple[str, str]:
    return STATUS_UI.get(s, (s, "neutral"))


contagem = dict(df.group_by("status").len().iter_rows())
n = df.height
mudancas = df.filter(pl.col("status") == "suggest_change")
sem_custo = contagem.get("sem_custo", 0)

# ---------------------------------------------------------------- estado vazio
# O caso comum hoje nao e "sem dado", e "avaliou tudo e nao pode opinar". Mostrar
# uma tabela vazia esconderia justamente a acao que destrava o produto.
if sem_custo == n:
    empty_state(
        f"Faltam os custos de compra dos {n} SKUs",
        "Sem o custo, não dá para separar preço que dá lucro de preço que dá prejuízo — "
        "então o motor se recusa a sugerir número, em vez de chutar.",
        "Com o custo preenchido, cada SKU passa a ter piso de margem (break-even) "
        "calculado e preço recomendado.",
    )
    st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:8px 0 20px'>",
                unsafe_allow_html=True)
    st.markdown("**SKUs aguardando custo**")
    st.dataframe(
        df.select([
            pl.col("sku").alias("SKU"),
            pl.col("current_price").alias("Preço hoje"),
            pl.col("n_competitors").alias("Concorrentes"),
        ]).to_pandas(),
        use_container_width=True, hide_index=True,
    )
    st.stop()

# --------------------------------------------------------------------- KPIs
ganho = mudancas.select(pl.col("ganho_relativo").drop_nulls()).to_series().to_list()
ganho_medio = (sum(ganho) / len(ganho)) if ganho else None
bloqueados = sum(contagem.get(k, 0) for k in ("locked", "inviavel", "sem_custo"))

kpi_row([
    ("SKUs avaliados", str(n), ""),
    ("Ajustes recomendados", str(mudancas.height),
     "preço muda" if mudancas.height else "nada a fazer hoje"),
    ("Ganho esperado médio", f"{ganho_medio:.2f}×".replace(".", ",") if ganho_medio else "—",
     "sobre o lucro esperado atual" if ganho_medio else ""),
    ("Precisam de atenção", str(bloqueados), "travados ou sem custo"),
])

st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:20px 0'>",
            unsafe_allow_html=True)

# ------------------------------------------------------------- tabela-decisao
st.markdown("### Recomendação por SKU")

tabela = df.select([
    "sku", "status", "titular_hoje", "current_price", "suggested_price",
    "p_win_atual", "p_win_sugerido", "margem_atual", "margem_sugerida",
    "ganho_relativo", "break_even", "n_competitors",
]).sort("status")

linhas = []
for r in tabela.iter_rows(named=True):
    label, estilo = _status(r["status"])
    papel = "—"
    if r["titular_hoje"] is not None:
        papel = "titular" if r["titular_hoje"] else "desafiante"
    # so ha seta quando o preco de fato muda: em `hold` o sugerido é igual ao
    # vigente, e uma seta ali sugeriria uma acao que nao existe
    seta = ""
    if r["suggested_price"] is not None and r["current_price"]:
        delta = r["suggested_price"] - r["current_price"]
        seta = "▲" if delta > 0.005 else ("▼" if delta < -0.005 else "=")
    linhas.append({
        "SKU": r["sku"],
        "Situação": label,
        "Papel": papel,
        "Preço hoje": fmt_brl(r["current_price"]),
        "Recomendado": f"{seta} {fmt_brl(r['suggested_price'])}" if r["suggested_price"] else "—",
        "P(buy box)": (f"{fmt_pct(r['p_win_atual'])} → {fmt_pct(r['p_win_sugerido'])}"
                       if r["p_win_sugerido"] is not None else fmt_pct(r["p_win_atual"])),
        "Margem": (f"{fmt_brl(r['margem_atual'])} → {fmt_brl(r['margem_sugerida'])}"
                   if r["margem_sugerida"] is not None else fmt_brl(r["margem_atual"])),
        "Ganho": f"{r['ganho_relativo']:.2f}×".replace(".", ",") if r["ganho_relativo"] else "—",
        "Break-even": fmt_brl(r["break_even"]),
        "Rivais": r["n_competitors"],
    })

st.dataframe(pl.from_dicts(linhas).to_pandas(), use_container_width=True, hide_index=True)

st.caption(
    "Titular e desafiante recebem recomendações opostas de propósito: quem já tem a buy box "
    "pode cobrar mais mantendo a mesma chance, então colhe margem; quem não tem, investe em "
    "conquistá-la. O ganho é relativo ao lucro esperado de hoje, não à receita."
)

# ------------------------------------------------------------------ drill-down
st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:24px 0 16px'>",
            unsafe_allow_html=True)
st.markdown("### Por que esse preço")

analisaveis = df.filter(pl.col("suggested_price").is_not_null())
if analisaveis.is_empty():
    st.info("Nenhum SKU com preço recomendado para detalhar nesta rodada.")
    st.stop()

sku = st.selectbox("SKU", analisaveis["sku"].to_list(), label_visibility="collapsed")
r = analisaveis.filter(pl.col("sku") == sku).row(0, named=True)

c1, c2, c3 = st.columns(3)
c1.markdown(f"**Situação**<br>{tag(*_status(r['status']))}", unsafe_allow_html=True)
c2.markdown(f"**Papel hoje**<br>{'Titular' if r['titular_hoje'] else 'Desafiante'}",
            unsafe_allow_html=True)
c3.markdown(f"**Concorrentes**<br>{r['n_competitors']}", unsafe_allow_html=True)

st.markdown(f"<div style='margin-top:14px'>{r['reason']}</div>", unsafe_allow_html=True)

# A curva e o argumento de existencia desta tela: o email mostra o numero, nao a
# forma. Reconstruida a partir dos pontos que o parquet ja carrega - sem chamar
# o modelo de novo, o que manteria a tela acoplada ao ETL.
atual, sugerido, be = r["current_price"], r["suggested_price"], r["break_even"]
if atual and sugerido and be:
    baixo, alto = atual * 0.85, atual * 1.15          # guard rail de +-15% por rodada
    pontos = []
    for i in range(61):
        p = baixo + (alto - baixo) * i / 60
        # interpola P(buy box) entre os dois pontos conhecidos, em log-preco:
        # o modelo e logit em ln(preco), entao a reta em log e a aproximacao certa
        if r["p_win_atual"] and r["p_win_sugerido"] and abs(sugerido - atual) > 0.01:
            t = (math.log(p) - math.log(atual)) / (math.log(sugerido) - math.log(atual))
            pw = r["p_win_atual"] + t * (r["p_win_sugerido"] - r["p_win_atual"])
            pw = min(max(pw, 0.0), 1.0)
        else:
            pw = r["p_win_atual"] or 0.0
        margem = (r["margem_atual"] or 0) + (p - atual) * 0.89   # liquido de comissao
        pontos.append({"preco": round(p, 2), "lucro": max(pw * margem, 0.0)})

    curva = pl.from_dicts(pontos).to_pandas()
    base = alt.Chart(curva).mark_line(color=ACCENT, strokeWidth=2).encode(
        x=alt.X("preco:Q", title="preço (R$)", scale=alt.Scale(zero=False)),
        y=alt.Y("lucro:Q", title="lucro esperado"),
        tooltip=["preco", "lucro"],
    )
    marcas = alt.Chart(
        pl.from_dicts([
            {"preco": atual, "o_que": "preço hoje"},
            {"preco": sugerido, "o_que": "recomendado"},
            {"preco": be, "o_que": "break-even"},
        ]).to_pandas()
    ).mark_rule(strokeDash=[4, 4], color=TEXT, opacity=0.5).encode(
        x="preco:Q", tooltip=["o_que", "preco"]
    )
    st.altair_chart((base + marcas).properties(height=260), use_container_width=True)
    st.caption(
        f"Faixa admissível desta rodada: {fmt_brl(baixo)} a {fmt_brl(alto)} "
        f"(guard rail de ±15% sobre o preço vigente). Abaixo de {fmt_brl(be)} a venda "
        "não cobre custo, tarifa e frete. A curva é uma aproximação entre os dois "
        "pontos que o motor calculou, não um novo cálculo."
    )
