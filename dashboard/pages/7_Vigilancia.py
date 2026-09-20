"""Vigilancia do catalogo comparavel.

A carteira deste cliente e de anuncio proprio: nao ha buy box a disputar na
pagina dele. O que existe e um catalogo PARECIDO, onde varios vendedores
disputam entre si - e e la que mora a ameaca, porque e a alternativa que o
comprador ve ao lado.

Entao a pergunta desta tela nao e "estou ganhando a buy box?", e sim: **quanto
acima do catalogo comparavel eu consigo cobrar, e esse espaco esta encolhendo?**
"""
import altair as alt
import polars as pl
import streamlit as st

from lib.theme import setup, ACCENT, TEXT, NEUTRAL_200, ACCENT_TINT_BG, ACCENT_TINT_TEXT
from lib.components import empty_state, fmt_brl, kpi_row, page_header, tag
from lib.r2_reader import (load_client_config, load_latest_market_snapshot,
                           load_market_history, sem_precos_absurdos)

def pct_br(v, casas: int = 1) -> str:
    """12.5 -> '12,5%'. So o numero troca de separador, nunca a frase em volta."""
    return f"{v:.{casas}f}%".replace(".", ",")


def delta_br(v) -> str:
    """Variacao assinada, em ponto percentual inteiro.

    Zera o sinal perto de zero: '-0%' parece defeito para quem le, mesmo sendo
    so o arredondamento de -0,06%.
    """
    if abs(v) < 0.5:
        return "0%"
    return f"{v:+.0f}%"


cfg = load_client_config()
setup("Vigilância")

page_header(
    "Vigilância de catálogo",
    "Seus anúncios não disputam buy box — mas competem com um catálogo parecido. "
    "Aqui está quanto você cobra acima dele, e se esse espaço está mudando.",
)

skus = cfg.get("skus") or []
comparaveis = tuple({s["catalog_comparavel"] for s in skus if s.get("catalog_comparavel")})

if not comparaveis:
    empty_state(
        "Nenhum catálogo comparável mapeado",
        "Cada SKU precisa estar ligado a um produto de catálogo equivalente para que "
        "exista com o que comparar.",
    )
    st.stop()

# Um comparavel que nao aparece na varredura de hoje nao deixou de existir: a
# coleta prioriza os mais vendidos de cada categoria e nem sempre alcanca todos.
# Usar so o dia de hoje daria um recorte enviesado - com poucos comparaveis, os
# que sobram nao representam a carteira. Por isso cada comparavel entra com a sua
# observacao mais recente, e a tela diz de quando ela e.
hist = sem_precos_absurdos(load_market_history(dias=12, produtos=comparaveis))
if hist.is_empty():
    empty_state("Sem dados de mercado", "A coleta ainda não trouxe ofertas para comparar.")
    st.stop()


def _mercado(pid: str):
    """Ofertas do comparavel na ultima data em que ele foi observado."""
    mk = hist.filter(pl.col("catalog_product_id") == pid)
    if mk.is_empty():
        return mk, None
    dia = mk["dia"].max()
    return mk.filter(pl.col("dia") == dia), dia


linhas = []
for s in skus:
    pid = s.get("catalog_comparavel")
    mk, dia = _mercado(pid) if pid else (pl.DataFrame(), None)
    preco = float(s["current_price"])
    if mk.is_empty():
        linhas.append({"sku": s["sku"], "titulo": s.get("titulo", ""), "preco": preco,
                       "vendidos": s.get("vendidos"), "coletado": False})
        continue
    precos = sorted(float(p) for p in mk["price"].to_list() if p)
    mediana = float(pl.Series(precos).median())
    menor = precos[0]
    linhas.append({
        "sku": s["sku"], "titulo": s.get("titulo", ""), "preco": preco, "coletado": True,
        "vendidos": s.get("vendidos"),
        "comparavel": pid, "n_ofertas": len(precos), "dia": dia,
        "mediana": mediana, "menor": menor,
        "premio_vs_mediana": 100 * (preco / mediana - 1),
        "premio_vs_menor": 100 * (preco / menor - 1),
    })

t = pl.from_dicts(linhas, infer_schema_length=None)
com_dado = t.filter(pl.col("coletado"))

if com_dado.is_empty():
    empty_state(
        "Os catálogos comparáveis ainda não foram coletados",
        "Eles entram na próxima rodada de coleta das suas categorias.",
    )
    st.stop()

# ------------------------------------------------------------------------ KPIs
acima = com_dado.filter(pl.col("premio_vs_mediana") > 0)
premio_mediano = float(com_dado["premio_vs_mediana"].median())
mais_exposto = com_dado.sort("premio_vs_menor", descending=True).row(0, named=True)

# Os anuncios de maior volume sao os que sustentam a operacao. O premio importa
# onde esta o volume, nao na contagem simples de SKUs - por isso o KPI olha so
# essa fatia.
FAIXA_ALTA = ("+10mil", "+5mil", "+1000")
volume = com_dado.filter(pl.col("vendidos").is_in(list(FAIXA_ALTA)))
n_volume = volume.height
n_volume_acima = volume.filter(pl.col("premio_vs_mediana") >= -0.5).height

kpi_row([
    ("SKUs com comparável", f"{com_dado.height}/{t.height}", "com observação recente"),
    ("Prêmio mediano", delta_br(premio_mediano), "sobre a mediana do catálogo"),
    ("Onde está o volume", f"{n_volume_acima}/{n_volume}",
     "dos mais vendidos cobram na mediana ou acima"),
    ("Maior exposição", mais_exposto["sku"],
     f"{delta_br(mais_exposto['premio_vs_menor'])} vs a oferta mais barata"),
])

st.markdown(
    f"<div style='background:{ACCENT_TINT_BG};border-left:4px solid {ACCENT};"
    f"padding:14px 18px;margin:18px 0 8px;font-size:14px;line-height:1.55'>"
    f"<b>Prêmio não é problema — é o ativo.</b> Vender fora do catálogo é o que permite "
    f"cobrar acima dele. O que vale acompanhar é se a distância está aumentando, porque aí "
    f"a alternativa mais barata fica cada vez mais visível ao lado do seu anúncio.</div>",
    unsafe_allow_html=True,
)

st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:20px 0'>",
            unsafe_allow_html=True)

# ------------------------------------------------------------------- panorama
st.markdown("### Sua posição contra cada catálogo comparável")

vista = []
for r in com_dado.sort("premio_vs_menor", descending=True).iter_rows(named=True):
    vista.append({
        "SKU": r["sku"],
        "Produto": (r["titulo"] or "")[:38],
        "Seu preço": fmt_brl(r["preco"]),
        "Mediana do catálogo": fmt_brl(r["mediana"]),
        "Mais barato": fmt_brl(r["menor"]),
        "vs mediana": delta_br(r["premio_vs_mediana"]),
        "vs mais barato": delta_br(r["premio_vs_menor"]),
        "Vendidos": r["vendidos"] or "—",
        "Ofertas": r["n_ofertas"],
        "Observado em": r["dia"],
    })
st.dataframe(pl.from_dicts(vista).to_pandas(), use_container_width=True, hide_index=True)

dias_obs = sorted({d for d in com_dado["dia"].to_list() if d})
if len(dias_obs) > 1:
    st.caption(
        f"Cada linha usa a observação mais recente daquele catálogo, entre {dias_obs[0]} e "
        f"{dias_obs[-1]}. A varredura diária prioriza os produtos mais vendidos de cada "
        "categoria, então nem todo comparável é alcançado todo dia."
    )

nao_coletados = t.filter(~pl.col("coletado"))
if not nao_coletados.is_empty():
    st.caption(
        f"{nao_coletados.height} SKU(s) ainda sem comparável observado: "
        + ", ".join(nao_coletados["sku"].to_list())
        + ". Entram assim que a coleta alcançar o produto equivalente."
    )

# ------------------------------------------------------------------ evolucao
st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:24px 0 16px'>",
            unsafe_allow_html=True)
st.markdown("### O espaço está encolhendo?")

sku_pick = st.selectbox("SKU", com_dado["sku"].to_list(), label_visibility="collapsed")
r = com_dado.filter(pl.col("sku") == sku_pick).row(0, named=True)

c1, c2, c3 = st.columns(3)
c1.markdown(f"**Seu preço**<br><span style='font-size:22px;font-weight:800'>{fmt_brl(r['preco'])}</span>",
            unsafe_allow_html=True)
c2.markdown(f"**Mediana do catálogo**<br><span style='font-size:22px;font-weight:800'>{fmt_brl(r['mediana'])}</span>",
            unsafe_allow_html=True)
c3.markdown(
    f"**Prêmio**<br><span style='font-size:22px;font-weight:800;color:{ACCENT}'>"
    f"{delta_br(r['premio_vs_mediana'])}</span>",
    unsafe_allow_html=True,
)

serie_hist = load_market_history(dias=10, produtos=(r["comparavel"],))
if serie_hist.is_empty() or serie_hist["dia"].n_unique() < 2:
    st.info(
        "Ainda não há dias suficientes coletados deste catálogo para mostrar tendência. "
        "A série aparece conforme as coletas diárias se acumulam."
    )
else:
    serie_hist = sem_precos_absurdos(serie_hist)
    serie = (
        serie_hist.group_by("dia")
        .agg(pl.col("price").median().alias("mediana"),
             pl.col("price").min().alias("menor"),
             pl.len().alias("ofertas"))
        .sort("dia")
    )
    longo = serie.unpivot(index="dia", on=["mediana", "menor"],
                          variable_name="serie", value_name="valor")
    linha = alt.Chart(longo.to_pandas()).mark_line(strokeWidth=2).encode(
        x=alt.X("dia:N", title=""),
        y=alt.Y("valor:Q", title="preço do catálogo (R$)", scale=alt.Scale(zero=False)),
        color=alt.Color("serie:N", title="",
                        scale=alt.Scale(domain=["mediana", "menor"], range=[TEXT, ACCENT])),
        tooltip=["dia", "serie", "valor"],
    )
    meu = alt.Chart(
        pl.DataFrame({"preco": [r["preco"]]}).to_pandas()
    ).mark_rule(strokeDash=[5, 4], color=ACCENT, opacity=0.7).encode(y="preco:Q")
    st.altair_chart((linha + meu).properties(height=280), use_container_width=True)

    primeiro = serie.row(0, named=True)
    ultimo = serie.row(serie.height - 1, named=True)
    var = 100 * (ultimo["mediana"] / primeiro["mediana"] - 1) if primeiro["mediana"] else 0
    if var < -0.5:
        movimento = f"caiu {pct_br(abs(var))}"
        leitura = "o espaço entre vocês aumentou, e a alternativa barata ficou mais visível."
    elif var > 0.5:
        movimento = f"subiu {pct_br(abs(var))}"
        leitura = "o espaço entre vocês diminuiu, o que reduz a pressão sobre o seu preço."
    else:
        movimento = "ficou estável"
        leitura = "o espaço entre vocês não mudou de forma relevante."
    st.caption(
        f"A linha tracejada é o seu preço. Entre {primeiro['dia']} e {ultimo['dia']}, "
        f"a mediana do catálogo comparável {movimento} — {leitura}"
    )

st.caption(
    "Comparável é um mapeamento nosso, não equivalência verificada: parte do prêmio pode ser "
    "diferença real de produto. Ofertas com preço acima de 20× a mediana do próprio catálogo "
    "são descartadas antes de qualquer conta."
)
