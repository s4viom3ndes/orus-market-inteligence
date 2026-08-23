from pathlib import Path
import streamlit as st
import polars as pl
import yaml
from lib.theme import setup, ACCENT, ACCENT_TINT_BG, ACCENT_TINT_TEXT
from lib.r2_reader import load_latest_market_snapshot, get_client, R2_BUCKET, list_snapshots, read_parquet

setup("Repricer")


@st.cache_data(ttl=300)
def load_mock_config() -> dict:
    try:
        obj = get_client().get_object(Bucket=R2_BUCKET, Key="state/mock_client.yaml")
        return yaml.safe_load(obj["Body"].read())
    except Exception:
        local = Path(__file__).parent.parent.parent / "etl" / "config" / "mock_client.yaml"
        return yaml.safe_load(local.read_text(encoding="utf-8"))


@st.cache_data(ttl=300)
def load_latest_suggestions() -> pl.DataFrame:
    snaps = list_snapshots("reprice_suggestions/")
    if not snaps:
        return pl.DataFrame()
    latest = max(snaps, key=lambda x: x["last_modified"])
    return read_parquet(latest["key"])


def project_pos(price: float, prices_sorted: list[float]) -> int:
    return sum(1 for p in prices_sorted if p < price)


st.markdown("<h1 style='font-size:34px;margin-bottom:6px'>Motor de Repricer</h1>", unsafe_allow_html=True)
st.markdown(
    "<div style='font-size:15px;opacity:0.6;margin-bottom:28px'>Sugestão automática de preço por SKU (regras determinísticas) + simulador interativo.</div>",
    unsafe_allow_html=True,
)

cfg = load_mock_config()
snap = load_latest_market_snapshot()
suggestions = load_latest_suggestions()

if snap.is_empty():
    st.warning("Sem snapshot.")
    st.stop()

st.markdown("<h3 style='margin:0 0 14px'>Sugestões atuais</h3>", unsafe_allow_html=True)
if suggestions.is_empty():
    st.info("Nenhuma sugestão gerada ainda. Rode `python -m jobs.run_repricer`.")
else:
    view = suggestions.select([
        "sku", "current_price", "winner_price", "min_price",
        "suggested_price", "status", "my_projected_position",
        "n_competitors", "reason",
    ])
    st.dataframe(view, use_container_width=True, hide_index=True)

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<h3 style='margin:24px 0 14px'>Simulador — que preço colocar?</h3>", unsafe_allow_html=True)

sku_names = [s["sku"] for s in cfg["skus"]]
sku_pick = st.selectbox("SKU", sku_names, label_visibility="collapsed")
sku_cfg = next(s for s in cfg["skus"] if s["sku"] == sku_pick)

offers = snap.filter(pl.col("catalog_product_id") == sku_cfg["catalog_product_id"]).sort("rank")
if offers.is_empty():
    st.warning("Sem ofertas no snapshot atual pra esse SKU.")
    st.stop()

prices = sorted(offers["price"].to_list())
winner_price = prices[0]
my_current = float(sku_cfg["current_price"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Meu preço atual", f"R$ {my_current:,.2f}")
c2.metric("Winner atual", f"R$ {winner_price:,.2f}")
c3.metric("Concorrentes", len(prices))
c4.metric("Minha posição hoje", f"{project_pos(my_current, prices) + 1}º")

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

min_slider = float(sku_cfg["min_price"])
max_slider = float(sku_cfg.get("max_price") or my_current * 1.5)
test_price = st.slider(
    "Preço simulado", min_value=min_slider, max_value=max_slider,
    value=my_current, step=0.10, format="R$ %.2f",
)

pos = project_pos(test_price, prices)
delta = pos - project_pos(my_current, prices)

c1, c2 = st.columns(2)
c1.metric("Posição projetada", f"{pos + 1}º", delta=f"{delta:+d} vs atual", delta_color="inverse")
if pos == 0:
    c2.markdown(
        f'<div style="background:{ACCENT_TINT_BG};padding:16px;border-left:4px solid {ACCENT}">'
        f'<b style="color:{ACCENT_TINT_TEXT}">Ganharia o Buy Box.</b> Winner atual: R$ {winner_price:,.2f}.'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("<h3 style='margin:24px 0 14px'>Curva preço × posição</h3>", unsafe_allow_html=True)
n_points = 40
step = (max_slider - min_slider) / (n_points - 1) if n_points > 1 else 1
curve = pl.DataFrame([{
    "preco": round(min_slider + i * step, 2),
    "posicao": project_pos(round(min_slider + i * step, 2), prices) + 1,
} for i in range(n_points)])
st.line_chart(curve.to_pandas().set_index("preco"))
st.caption(f"Curva desce quando você fica melhor colocado. Min_price = R$ {min_slider:.2f}, winner = R$ {winner_price:,.2f}.")
