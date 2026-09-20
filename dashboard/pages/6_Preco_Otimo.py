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

from lib import tarifas as tar
from lib.theme import setup, ACCENT, ACCENT_TINT_BG, TEXT, NEUTRAL_200
from lib.components import (empty_state, fmt_brl, fmt_pct, kpi_row, page_header, tag)
from lib.r2_reader import load_client_config, load_latest_optimizer, seller_do_config

cfg = load_client_config()
setup("Preço Ótimo", *seller_do_config(cfg))

# O codigo do anuncio nao diz nada a quem le. Onde houver titulo cadastrado, ele
# substitui o codigo na tela.
_rotulo = {s_["sku"]: (s_.get("titulo") or s_["sku"])[:46]
           for s_ in (cfg.get("skus") or [])}

page_header(
    "Preço ótimo",
    "O preço que equilibra vender bem e ganhar bem — não o mais barato, nem o mais caro.",
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

# ------------------------------------------------- explicacao + simulador
# O caminho comum hoje e "avaliou tudo e nao pode opinar", por falta do custo de
# compra. Em vez de uma tarja de alerta - que num painel de cliente passa
# impressao de defeito - a tela explica o conceito e entrega o simulador, para a
# conta poder ser feita na hora em que o custo aparecer.
if sem_custo == n:
    st.markdown(
        f"<div style='font-size:15px;line-height:1.7;max-width:820px'>"
        f"<b>Preço ótimo não é o preço que mais vende, nem o que dá mais margem.</b> "
        f"É o que equilibra os dois. Cobrar pouco quase sempre garante a venda, mas pode "
        f"não sobrar nada; cobrar muito protege a margem de cada venda e custa as vendas. "
        f"O ponto ótimo fica entre os dois extremos."
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='font-size:15px;line-height:1.7;max-width:820px;margin-top:14px'>"
        f"Para achar esse ponto, a conta leva em consideração três coisas: <b>quanto o "
        f"mercado está cobrando</b> pelo produto equivalente, <b>o quanto o seu anúncio "
        f"tende a ser escolhido</b> em cada faixa de preço, e <b>o que sobra para você</b> "
        f"depois da comissão do Mercado Livre, da taxa fixa e do frete."
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"<div style='background:{ACCENT_TINT_BG};border-left:4px solid {ACCENT};"
        f"padding:16px 20px;margin:22px 0 8px;max-width:820px;font-size:14px;line-height:1.65'>"
        f"A única peça que falta é <b>quanto você paga ao fornecedor</b>. Sem ela dá para "
        f"dizer onde você está no mercado, mas não se um preço compensa — e um preço que "
        f"ganha posição vendendo no prejuízo não interessa a ninguém. "
        f"Use o simulador abaixo para ver a conta com o seu número."
        f"</div>",
        unsafe_allow_html=True,
    )

    st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:24px 0 18px'>",
                unsafe_allow_html=True)
    st.markdown("### Simule com o seu custo")

    c1, c2 = st.columns([1, 1])
    with c1:
        sku_sim = st.selectbox(
            "Produto",
            df["sku"].to_list(),
            format_func=lambda k: _rotulo.get(k, k),
        )
    linha = df.filter(pl.col("sku") == sku_sim).row(0, named=True)
    preco_atual = float(linha["current_price"])
    with c2:
        custo = st.number_input(
            "Quanto você paga ao fornecedor (R$)",
            min_value=0.0, max_value=float(max(preco_atual * 3, 10.0)),
            value=round(preco_atual * 0.35, 2), step=1.0, format="%.2f",
        )

    piso = tar.break_even(custo)
    sobra = tar.margem(preco_atual, custo)
    sobra_pct = (sobra / preco_atual * 100) if preco_atual else 0

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    kpi_row([
        ("Seu preço hoje", fmt_brl(preco_atual), ""),
        ("Preço mínimo para não ter prejuízo", fmt_brl(piso),
         "abaixo disso a venda custa dinheiro"),
        ("Sobra por unidade vendida", fmt_brl(sobra),
         f"{sobra_pct:.0f}% do preço".replace(".", ",")),
    ])

    if sobra <= 0:
        st.markdown(
            f"<div style='background:{ACCENT_TINT_BG};border-left:4px solid {ACCENT};"
            f"padding:14px 18px;margin-top:16px;max-width:820px;font-size:14px'>"
            f"Com esse custo, o preço de hoje <b>não cobre</b> a operação. O mínimo "
            f"seria {fmt_brl(piso)}.</div>",
            unsafe_allow_html=True,
        )
    else:
        folga = preco_atual - piso
        st.markdown(
            f"<div style='margin-top:16px;max-width:820px;font-size:14px;line-height:1.65'>"
            f"Com esse custo, o preço de hoje tem <b>{fmt_brl(folga)}</b> de folga sobre o "
            f"mínimo. Essa folga é o espaço real que existe para promoção, cupom ou reação "
            f"a um concorrente — sem ela, qualquer desconto sai do seu bolso.</div>",
            unsafe_allow_html=True,
        )

    with st.expander("O que já está embutido nessa conta"):
        st.markdown(
            f"""
| Item | Valor usado |
|---|---|
| Comissão do Mercado Livre (anúncio clássico) | {100*tar.COMISSAO_CLASSICO:.0f}% do preço |
| Comissão do anúncio premium | {100*tar.COMISSAO_PREMIUM:.0f}% do preço |
| Taxa fixa por unidade, abaixo de {fmt_brl(tar.LIMIAR_FRETE)} | {fmt_brl(tar.TAXA_FIXA)} |
| Frete por conta do vendedor, a partir de {fmt_brl(tar.LIMIAR_FRETE)} | {fmt_brl(tar.CUSTO_FRETE)} |

Estes são valores de mercado, **não a sua tabela**. Vale conferir contra a sua fatura —
e, com a conta conectada, o próprio Mercado Livre informa a tarifa real de cada anúncio,
o que substitui estes números.
"""
        )

    st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:26px 0 16px'>",
                unsafe_allow_html=True)
    st.markdown("### Seus produtos acompanhados")
    st.dataframe(
        df.select([
            pl.col("sku").replace_strict(_rotulo, default=None).alias("Produto"),
            pl.col("current_price").map_elements(fmt_brl, return_dtype=pl.String).alias("Preço hoje"),
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
        "Produto": _rotulo.get(r["sku"], r["sku"]),
        "Situação": label,
        "Papel": papel,
        "Preço hoje": fmt_brl(r["current_price"]),
        "Recomendado": f"{seta} {fmt_brl(r['suggested_price'])}" if r["suggested_price"] else "—",
        "P(buy box)": (f"{fmt_pct(r['p_win_atual'])} → {fmt_pct(r['p_win_sugerido'])}"
                       if r["p_win_sugerido"] is not None else fmt_pct(r["p_win_atual"])),
        "Margem": (f"{fmt_brl(r['margem_atual'])} → {fmt_brl(r['margem_sugerida'])}"
                   if r["margem_sugerida"] is not None else fmt_brl(r["margem_atual"])),
        "Ganho": f"{r['ganho_relativo']:.2f}×".replace(".", ",") if r["ganho_relativo"] else "—",
        "Preço mínimo": fmt_brl(r["break_even"]),
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

sku = st.selectbox("Produto", analisaveis["sku"].to_list(),
                   format_func=lambda k: _rotulo.get(k, k), label_visibility="collapsed")
r = analisaveis.filter(pl.col("sku") == sku).row(0, named=True)

c1, c2 = st.columns(2)
c1.markdown(f"**Situação**<br>{tag(*_status(r['status']))}", unsafe_allow_html=True)
c2.markdown(f"**Posição hoje**<br>{'Com o destaque' if r['titular_hoje'] else 'Sem o destaque'}",
            unsafe_allow_html=True)

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
