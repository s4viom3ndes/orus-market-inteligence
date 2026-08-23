from pathlib import Path
import streamlit as st
import polars as pl
import yaml
from lib.theme import setup, DIVIDER
from lib.components import (
    vip_zone_open, vip_zone_close, sku_card,
    competitor_row, reversion_callout, locked_callout,
)
from lib.r2_reader import load_latest_market_snapshot, get_client, R2_BUCKET

setup("Buy Box Monitor")


@st.cache_data(ttl=300)
def load_mock_config() -> dict:
    try:
        obj = get_client().get_object(Bucket=R2_BUCKET, Key="state/mock_client.yaml")
        return yaml.safe_load(obj["Body"].read())
    except Exception:
        local = Path(__file__).parent.parent.parent / "etl" / "config" / "mock_client.yaml"
        return yaml.safe_load(local.read_text(encoding="utf-8"))


cfg = load_mock_config()
seller = cfg["seller"]

st.markdown(
    f"<h1 style='font-size:34px;margin-bottom:6px'>Buy Box Monitor — {seller['name']}</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<div style='font-size:15px;opacity:0.6;margin-bottom:28px'>Comparação dos SKUs do cliente contra os winners atuais do mercado.</div>",
    unsafe_allow_html=True,
)

df = load_latest_market_snapshot()
if df.is_empty():
    st.warning("Sem snapshot.")
    st.stop()

skus = cfg["skus"]
skus_data = []
for sku in skus:
    pid = sku["catalog_product_id"]
    offers = df.filter(pl.col("catalog_product_id") == pid).sort("rank")
    if offers.is_empty():
        skus_data.append({**sku, "status": ("no_data", "outline"), "winner": None,
                          "my_pos": None, "n": 0, "gap": None})
        continue
    winner = offers.row(0, named=True)
    my_price = float(sku["current_price"])
    prices = offers["price"].to_list()
    our_pos = sum(1 for p in prices if p < my_price)
    gap = round(my_price - float(winner["price"]), 2)

    if our_pos == 0:
        status = ("GANHANDO", "neutral")
    elif winner["price"] - 0.01 >= sku["min_price"]:
        status = ("PODE RECUPERAR", "accent")
    else:
        status = ("TRAVADO", "outline")

    skus_data.append({
        **sku, "status": status, "winner": winner, "my_pos": our_pos + 1,
        "n": offers.height, "gap": gap,
    })


vip_zone_open("Seus SKUs monitorados")
for i in range(0, len(skus_data), 2):
    cols = st.columns(2)
    for j, s in enumerate(skus_data[i:i+2]):
        with cols[j]:
            winner_price = float(s["winner"]["price"]) if s["winner"] else 0.0
            product_name = (s["winner"].get("product_name") if s["winner"] else s.get("product_hint")) or s["sku"]
            sku_card(
                kicker=s["sku"],
                title=product_name[:55],
                status_label=s["status"][0],
                status_style=s["status"][1],
                my_price=float(s["current_price"]),
                winner_price=winner_price,
                gap=s["gap"] or 0.0,
                n_competitors=s["n"],
                position=s["my_pos"] or 0,
            )
vip_zone_close()

st.markdown("<hr>", unsafe_allow_html=True)
st.markdown("<h3 style='margin:24px 0 14px'>Ofertas concorrentes por SKU</h3>", unsafe_allow_html=True)

sku_names = [s["sku"] for s in skus]
selected = st.selectbox("Detalhar SKU", sku_names, label_visibility="collapsed")
sku_cfg = next(s for s in skus if s["sku"] == selected)
offers = df.filter(pl.col("catalog_product_id") == sku_cfg["catalog_product_id"]).sort("rank")

if offers.is_empty():
    st.info("Sem ofertas no snapshot atual pra esse produto de catálogo.")
else:
    my_price = float(sku_cfg["current_price"])
    my_seller_id = seller.get("ml_seller_id")
    top_offers = offers.head(15)
    inserted_me = False
    winner_price = float(top_offers.row(0, named=True)["price"])

    for i, r in enumerate(top_offers.rows(named=True), 1):
        is_you = int(r["seller_id"]) == int(my_seller_id) if my_seller_id else False
        competitor_row(
            rank=i,
            seller=r["seller_id"],
            price=float(r["price"]),
            delta_vs_you=float(r["price"]) - my_price,
            is_you=is_you,
        )
        if is_you:
            inserted_me = True

    if not inserted_me:
        my_pos = sum(1 for p in offers["price"].to_list() if p < my_price)
        competitor_row(
            rank=my_pos + 1,
            seller=f"{seller['name']}",
            price=my_price,
            delta_vs_you=0.0,
            is_you=True,
        )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    min_p = float(sku_cfg["min_price"])
    if winner_price - 0.01 >= min_p:
        margin_headroom = round(my_price - min_p, 2)
        target = round(winner_price - 0.01, 2)
        reversion_callout(margin_headroom, target, my_price)
    else:
        locked_callout(min_p, winner_price)
