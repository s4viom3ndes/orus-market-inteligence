"""Como o acompanhamento diario aparece ao longo do tempo.

A serie real dos anuncios do cliente ainda esta sendo acumulada. Enquanto isso,
esta tela mostra a FORMA que o acompanhamento assume - com uma curva ilustrativa
por produto, rotulada como exemplo em todo lugar onde aparece.

Assim que houver historico medido suficiente, a curva de exemplo sai e o dado
real entra no lugar, sem mudar o desenho da tela.
"""
import altair as alt
import polars as pl
import streamlit as st

from lib.theme import setup, ACCENT, TEXT, NEUTRAL_200, ACCENT_TINT_BG, ACCENT_TINT_TEXT
from lib.components import fmt_brl, kpi_row, page_header
from lib.r2_reader import load_client_config, seller_do_config
from lib.simulacao import serie_ilustrativa

cfg = load_client_config()
setup("Histórico", *seller_do_config(cfg))

page_header(
    "Acompanhamento no tempo",
    "Um preço isolado diz pouco. O que muda a decisão é ver o movimento: quando a "
    "concorrência se aproxima, quando se afasta, e há quanto tempo isso vem acontecendo.",
)

skus = [s for s in (cfg.get("skus") or []) if s.get("current_price")]
if not skus:
    st.info("Nenhum produto cadastrado para acompanhar.")
    st.stop()

# ----------------------------------------------------------- aviso obrigatorio
st.markdown(
    f"<div style='background:{ACCENT_TINT_BG};border-left:4px solid {ACCENT};"
    f"padding:16px 20px;margin-bottom:26px;max-width:860px'>"
    f"<div style='font-family:Archivo,sans-serif;font-weight:800;font-size:15px;"
    f"color:{ACCENT_TINT_TEXT};margin-bottom:6px'>Exemplo ilustrativo</div>"
    f"<div style='font-size:14px;line-height:1.6'>"
    f"As curvas desta página <b>não são medições</b> — são um exemplo de como o "
    f"acompanhamento fica depois de algumas semanas. Os preços dos seus anúncios são reais; "
    f"a variação do concorrente ao longo dos dias é simulada, porque o histórico dos seus "
    f"produtos começou a ser registrado agora."
    f"</div></div>",
    unsafe_allow_html=True,
)

rotulos = {s["sku"]: (s.get("titulo") or s["sku"])[:48] for s in skus}
escolhido = st.selectbox("Produto", [s["sku"] for s in skus],
                         format_func=lambda k: rotulos.get(k, k),
                         label_visibility="collapsed")
sku_cfg = next(s for s in skus if s["sku"] == escolhido)

serie = serie_ilustrativa(
    escolhido,
    float(sku_cfg["current_price"]),
    dias=30,
    preco_tabela=float(sku_cfg["preco_tabela"]) if sku_cfg.get("preco_tabela") else None,
)

ultimo = serie.row(serie.height - 1, named=True)
menor_conc = float(serie["concorrente"].min())
dias_a_frente = serie.filter(pl.col("diferenca") > 0).height

kpi_row([
    ("Seu preço", fmt_brl(sku_cfg["current_price"]), "estável no período"),
    ("Concorrente hoje", fmt_brl(ultimo["concorrente"]),
     "mais barato que você" if ultimo["diferenca"] > 0 else "mais caro que você"),
    ("Menor preço do concorrente", fmt_brl(menor_conc), "nos últimos 30 dias"),
    ("Dias em que ficou acima dele", f"{dias_a_frente}/30", ""),
])

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

longo = serie.unpivot(index="data", on=["seu_preco", "concorrente"],
                      variable_name="serie", value_name="valor")
longo = longo.with_columns(
    pl.col("serie").replace_strict({"seu_preco": "Seu preço",
                                    "concorrente": "Concorrente"}).alias("serie")
)

grafico = alt.Chart(longo.to_pandas()).mark_line(strokeWidth=2.5).encode(
    x=alt.X("data:T", title=""),
    y=alt.Y("valor:Q", title="preço (R$)", scale=alt.Scale(zero=False)),
    color=alt.Color("serie:N", title="",
                    scale=alt.Scale(domain=["Seu preço", "Concorrente"],
                                    range=[TEXT, ACCENT])),
    tooltip=["data:T", "serie:N", "valor:Q"],
).properties(height=300)
st.altair_chart(grafico, use_container_width=True)
st.caption(
    "Curva de exemplo. O seu preço aparece estável porque é assim que a maioria dos "
    "vendedores opera — quem se move é a concorrência, e é justamente esse movimento "
    "que passa despercebido sem acompanhamento diário."
)

# ------------------------------------------------------------------ panorama
st.markdown(f"<hr style='border-top:2px solid {NEUTRAL_200};margin:26px 0 16px'>",
            unsafe_allow_html=True)
st.markdown("### Como ficaria a sua carteira inteira")

resumo = []
for s in skus:
    ser = serie_ilustrativa(
        s["sku"], float(s["current_price"]), dias=30,
        preco_tabela=float(s["preco_tabela"]) if s.get("preco_tabela") else None,
    )
    u = ser.row(ser.height - 1, named=True)
    resumo.append({
        "Produto": rotulos.get(s["sku"], s["sku"]),
        "Seu preço": fmt_brl(s["current_price"]),
        "Concorrente hoje": fmt_brl(u["concorrente"]),
        "Menor no período": fmt_brl(float(ser["concorrente"].min())),
        "Dias acima dele": f"{ser.filter(pl.col('diferenca') > 0).height}/30",
    })
st.dataframe(pl.from_dicts(resumo).to_pandas(), use_container_width=True, hide_index=True)
st.caption(
    "Mesma ressalva: os seus preços são reais, a variação do concorrente é ilustrativa. "
    "Com a medição diária em curso, esta tabela passa a refletir o que aconteceu de fato."
)
