import json
from pathlib import Path
import streamlit as st
import polars as pl
import yaml
from lib.r2_reader import load_latest_market_snapshot, load_buy_box_state

st.set_page_config(page_title="Buy Box Monitor", page_icon="🏆", layout="wide")
st.title("🏆 Buy Box Monitor - VariedadesSB (mock)")
st.caption("Comparacao dos SKUs do cliente contra os winners atuais do mercado.")

MOCK_CFG = Path(__file__).parent.parent.parent / "etl" / "config" / "mock_client.yaml"
cfg = yaml.safe_load(MOCK_CFG.read_text(encoding="utf-8"))

seller = cfg["seller"]
skus = cfg["skus"]

st.write(f"**Vendedor**: {seller['name']} | ML seller_id: `{seller['ml_seller_id']}`")

df = load_latest_market_snapshot()
if df.is_empty():
    st.warning("Sem snapshots.")
    st.stop()

state = load_buy_box_state()

rows = []
for sku in skus:
    pid = sku["catalog_product_id"]
    offers = df.filter(pl.col("catalog_product_id") == pid).sort("rank")
    if offers.is_empty():
        rows.append({**sku, "status": "sem dado no snapshot atual"})
        continue
    winner = offers.row(0, named=True)
    my_price = float(sku["current_price"])
    prices = offers["price"].to_list()
    our_pos = sum(1 for p in prices if p < my_price)
    gap = round(my_price - float(winner["price"]), 2)

    if our_pos == 0:
        status = "🟢 GANHANDO"
    elif winner["price"] - 0.01 >= sku["min_price"]:
        status = "🟡 PODE RECUPERAR (baixar preco)"
    else:
        status = "🔴 TRAVADO (winner < min_price)"

    rows.append({
        "SKU": sku["sku"],
        "Produto": winner.get("product_name", "")[:50],
        "Meu preco": f"R$ {my_price:.2f}",
        "Winner": f"R$ {winner['price']:.2f}",
        "Gap": f"R$ {gap:+.2f}",
        "Concorrentes": offers.height,
        "Posicao atual (se preco mantido)": our_pos + 1,
        "Status": status,
    })

st.dataframe(pl.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Ofertas concorrentes por SKU")
selected = st.selectbox("Detalhar SKU", [s["sku"] for s in skus])
sku_cfg = next(s for s in skus if s["sku"] == selected)
offers = df.filter(pl.col("catalog_product_id") == sku_cfg["catalog_product_id"]).sort("rank")

if not offers.is_empty():
    st.dataframe(
        offers.select([
            "rank", "seller_id", "price", "shipping_logistic_type",
            "shipping_free", "condition", "listing_type_id"
        ]),
        use_container_width=True, hide_index=True
    )

    st.info(
        f"**Sua config**: preco atual R$ {sku_cfg['current_price']:.2f} | "
        f"min_price R$ {sku_cfg['min_price']:.2f} | target_position = {sku_cfg['target_position']}"
    )
