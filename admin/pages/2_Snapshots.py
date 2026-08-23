import streamlit as st
import polars as pl
from lib.r2 import list_objects, read_parquet

st.set_page_config(page_title="Snapshots", page_icon="📦", layout="wide")
st.title("📦 Snapshots no R2")

prefix = st.selectbox("Dataset", ["market_offers/", "trends/"])
objs = sorted(list_objects(prefix), key=lambda x: x["last_modified"], reverse=True)

if not objs:
    st.info("Nenhum snapshot.")
    st.stop()

st.write(f"**{len(objs)} snapshots** — total {sum(o['size'] for o in objs)/(1024*1024):.2f} MB")

df = pl.DataFrame([{
    "key": o["key"],
    "size_kb": round(o["size"] / 1024, 1),
    "when": o["last_modified"].strftime("%Y-%m-%d %H:%M UTC"),
} for o in objs])
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Inspecionar um snapshot")
key = st.selectbox("Escolha", [o["key"] for o in objs])

if st.button("Carregar"):
    with st.spinner(f"Baixando {key}..."):
        pdf = read_parquet(key)
    st.write(f"**{pdf.height:,} linhas × {pdf.width} colunas**")
    st.dataframe(pdf.head(200), use_container_width=True)

    with st.expander("Schema"):
        st.write(pdf.schema)

    numeric = [c for c in pdf.columns if pdf.schema[c] in (pl.Int64, pl.Float64, pl.Int32, pl.Float32)]
    if numeric:
        with st.expander("Describe (numericas)"):
            st.dataframe(pdf.select(numeric).describe(), use_container_width=True)
