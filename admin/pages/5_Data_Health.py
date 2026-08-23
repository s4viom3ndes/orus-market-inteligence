import datetime
import json
import streamlit as st
import polars as pl
from lib.r2 import get_client, R2_BUCKET, list_objects, get_json

st.set_page_config(page_title="Data Health", page_icon="🩺", layout="wide")
st.title("🩺 Data Health")
st.caption("Metricas de qualidade por dataset. Computadas em cada write + summary cross-dataset.")


@st.cache_data(ttl=60)
def load_summary() -> dict | None:
    try:
        return get_json("state/data_health/_summary_latest.json")
    except Exception:
        return None


@st.cache_data(ttl=60)
def load_latest_per_dataset() -> list[dict]:
    objs = list_objects("state/data_health/")
    out = []
    for o in objs:
        k = o["key"]
        if k.endswith("_latest.json") and "/history/" not in k and "_summary_" not in k:
            try:
                out.append(get_json(k))
            except Exception:
                pass
    return sorted(out, key=lambda x: x.get("dataset", ""))


summary = load_summary()
if summary:
    findings = summary.get("critical_findings") or []
    if findings:
        st.error("**Problemas criticos detectados:**\n" + "\n".join(f"- {f}" for f in findings))
    else:
        st.success("Todos datasets healthy no ultimo check.")
    st.caption(f"Ultimo check: {datetime.datetime.fromtimestamp(summary['checked_at'])}")

datasets = load_latest_per_dataset()
if not datasets:
    st.warning("Nenhum health snapshot ainda. Rode `python -m jobs.check_data_health` ou aguarde proxima coleta.")
    st.stop()

st.divider()
st.subheader("Estado por dataset")

cols = st.columns(min(len(datasets), 3))
for i, d in enumerate(datasets):
    with cols[i % len(cols)]:
        emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(d.get("status", "?"), "⚪")
        st.metric(
            f"{emoji} {d['dataset']}",
            d.get("status", "?"),
            f"{d['row_count']:,} linhas" if d.get("row_count") else "-",
        )
        st.caption(f"computed: {d.get('computed_at_iso', '?')}")
        warnings = d.get("warnings") or []
        if warnings:
            for w in warnings:
                st.warning(w)

st.divider()

for d in datasets:
    with st.expander(f"Detalhes: **{d['dataset']}**"):
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Numeric stats**")
            st.json(d.get("numeric_stats", {}))
        with c2:
            st.write("**Null rates (top 10 mais nulos)**")
            nulls = d.get("null_rates", {}) or {}
            top = sorted(nulls.items(), key=lambda x: x[1], reverse=True)[:10]
            st.dataframe(
                pl.DataFrame([{"coluna": k, "pct_null": round(v*100, 2)} for k, v in top]),
                use_container_width=True, hide_index=True,
            )

        st.write("**Unique counts (top 10)**")
        uc = d.get("unique_counts", {}) or {}
        st.dataframe(
            pl.DataFrame([{"coluna": k, "n_unique": v} for k, v in sorted(uc.items(), key=lambda x: x[1], reverse=True)[:10]]),
            use_container_width=True, hide_index=True,
        )
