import streamlit as st
import polars as pl
from auth.db import get_session
from auth.models import MLAccount, ClientSku

st.set_page_config(page_title="Orus - Meus SKUs", layout="centered")
st.title("Meus SKUs monitorados")

user_id_str = st.text_input("user_id (dev only)", value="1")
try:
    user_id = int(user_id_str)
except ValueError:
    st.stop()

with get_session() as db:
    accounts = db.query(MLAccount).filter_by(user_id=user_id, is_active=True).all()

if not accounts:
    st.warning("Nenhuma conta ML vinculada ainda. Va em Link ML.")
    st.stop()

acc = st.selectbox("Conta ML", accounts, format_func=lambda a: f"{a.ml_nickname} ({a.ml_user_id})")

with get_session() as db:
    skus = db.query(ClientSku).filter_by(ml_account_id=acc.id).all()

if skus:
    st.dataframe(
        pl.DataFrame([{
            "sku": s.sku, "catalog_product_id": s.catalog_product_id,
            "category_id": s.category_id, "current_price": s.current_price,
            "min_price": s.min_price, "max_price": s.max_price,
            "strategy": s.strategy, "target_position": s.target_position,
        } for s in skus]),
        use_container_width=True, hide_index=True,
    )
else:
    st.info("Nenhum SKU cadastrado.")

st.divider()
st.subheader("Adicionar SKU")

with st.form("add_sku"):
    sku = st.text_input("SKU interno (ex: SR-INOX-001)")
    catalog_pid = st.text_input("catalog_product_id ML (ex: MLB24665401)")
    category_id = st.text_input("category_id ML (ex: MLB193633)")
    hint = st.text_input("Product hint (opcional)")
    current_price = st.number_input("Preço atual", min_value=0.0, step=0.10)
    min_price = st.number_input("Preço mínimo", min_value=0.0, step=0.10)
    max_price = st.number_input("Preço máximo (opcional)", min_value=0.0, step=0.10)

    if st.form_submit_button("Adicionar", type="primary"):
        if not (sku and catalog_pid and current_price > 0 and min_price > 0):
            st.error("Preencha SKU, catalog_product_id, preço atual e mínimo")
        else:
            with get_session() as db:
                new = ClientSku(
                    ml_account_id=acc.id, sku=sku, catalog_product_id=catalog_pid,
                    category_id=category_id or None, product_hint=hint or None,
                    current_price=current_price, min_price=min_price,
                    max_price=max_price if max_price > 0 else None,
                )
                db.add(new)
                db.commit()
            st.success(f"SKU {sku} adicionado.")
            st.rerun()
