import io
from pathlib import Path
import streamlit as st
import polars as pl
import yaml
from lib.r2_reader import (
    load_latest_market_snapshot,
    get_client,
    R2_BUCKET,
    list_snapshots,
    read_parquet,
)

st.set_page_config(page_title="Repricer", page_icon="💰", layout="wide")
st.title("💰 Motor de Repricer + Simulador")
st.caption("Sugestoes automaticas de preco por SKU + simulador interativo do impacto.")


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


def simulate(price: float, prices_sorted: list[float]) -> int:
    return sum(1 for p in prices_sorted if p < price)


cfg = load_mock_config()
snap = load_latest_market_snapshot()
suggestions = load_latest_suggestions()

if snap.is_empty():
    st.warning("Sem snapshot de mercado.")
    st.stop()

st.subheader("Sugestoes atuais")
if suggestions.is_empty():
    st.info("Nenhuma sugestao gerada ainda. Rode `python -m jobs.run_repricer`.")
else:
    view = suggestions.select([
        "sku", "current_price", "winner_price", "min_price",
        "suggested_price", "status", "my_projected_position",
        "n_competitors", "reason",
    ])
    st.dataframe(view, use_container_width=True, hide_index=True)

st.divider()
st.subheader("🎛️ Simulador — que preço colocar?")

sku_names = [s["sku"] for s in cfg["skus"]]
sku_pick = st.selectbox("SKU", sku_names)
sku_cfg = next(s for s in cfg["skus"] if s["sku"] == sku_pick)

offers = snap.filter(pl.col("catalog_product_id") == sku_cfg["catalog_product_id"]).sort("rank")
if offers.is_empty():
    st.warning("Este SKU nao esta no snapshot atual (mercado sem ofertas hoje).")
    st.stop()

prices = sorted(offers["price"].to_list())
winner_price = prices[0]
my_current = float(sku_cfg["current_price"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Meu preco atual", f"R$ {my_current:.2f}")
c2.metric("Winner atual", f"R$ {winner_price:.2f}")
c3.metric("Concorrentes", len(prices))
c4.metric("Minha posicao hoje", simulate(my_current, prices) + 1)

st.write("**Escolha um preço para simular:**")
min_slider = float(sku_cfg["min_price"])
max_slider = float(sku_cfg.get("max_price", my_current * 1.5))
test_price = st.slider(
    "Preco simulado",
    min_value=min_slider,
    max_value=max_slider,
    value=my_current,
    step=0.10,
    format="R$ %.2f",
)

pos = simulate(test_price, prices)
st.metric(
    "Posicao projetada",
    f"{pos + 1}º",
    delta=f"{pos - simulate(my_current, prices):+d} vs atual",
    delta_color="inverse",
)
if pos == 0:
    st.success(f"🏆 Ganharia o Buy Box! (winner atual = R$ {winner_price:.2f})")
elif pos <= 2:
    st.info(f"Top 3 — competitivo. Winner ainda seria R$ {winner_price:.2f}")
else:
    st.warning(f"Posicao {pos+1}º entre {len(prices)}. Muito distante do winner.")

st.divider()
st.subheader("Curva preço × posição")

n_points = 40
step = (max_slider - min_slider) / (n_points - 1)
curve = [{
    "preco": round(min_slider + i * step, 2),
    "posicao": simulate(round(min_slider + i * step, 2), prices) + 1,
} for i in range(n_points)]
curve_df = pl.DataFrame(curve)

st.line_chart(curve_df.to_pandas().set_index("preco"))
st.caption(
    "Onde a curva cai pra 1 = seu preço ganharia buy box. "
    f"Seu min_price = R$ {min_slider:.2f}. Winner hoje = R$ {winner_price:.2f}."
)

st.divider()
st.subheader("Ofertas concorrentes agora")
st.dataframe(
    offers.select([
        "rank", "seller_id", "price", "shipping_logistic_type",
        "shipping_free", "condition", "listing_type_id"
    ]).head(20),
    use_container_width=True, hide_index=True,
)
