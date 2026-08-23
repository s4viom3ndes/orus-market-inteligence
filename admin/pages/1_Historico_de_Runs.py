import streamlit as st
import polars as pl
from lib.r2 import list_objects, get_json

st.set_page_config(page_title="Historico de Runs", page_icon="📜", layout="wide")
st.title("📜 Historico de Runs")

hist = list_objects("state/job_status/history/")
if not hist:
    st.info("Nenhum historico ainda.")
    st.stop()

by_job: dict[str, list[dict]] = {}
for o in hist:
    fname = o["key"].split("/")[-1]
    job_name = fname.rsplit("_", 1)[0]
    by_job.setdefault(job_name, []).append(o)

job_pick = st.selectbox("Job", sorted(by_job.keys()))
runs = sorted(by_job[job_pick], key=lambda x: x["last_modified"], reverse=True)[:100]

rows = []
for r in runs:
    j = get_json(r["key"])
    row = {
        "when": j.get("started_at_iso"),
        "status": j.get("status"),
        "duration_s": j.get("duration_sec"),
    }
    for k in ("rows", "categories_ok", "unique_products", "unique_sellers",
              "watched_hits", "skus_avaliados", "changes", "leaves"):
        v = (j.get("counts") or {}).get(k)
        if v is not None:
            row[k] = v
    rows.append(row)

df = pl.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("Duracao ao longo do tempo")
durs = df.filter(pl.col("duration_s").is_not_null()).sort("when")
if durs.height >= 2:
    st.line_chart(durs.select(["when", "duration_s"]).to_pandas().set_index("when"))

if "rows" in df.columns:
    st.subheader("Volume coletado ao longo do tempo")
    vol = df.filter(pl.col("rows").is_not_null()).sort("when")
    if vol.height >= 2:
        st.line_chart(vol.select(["when", "rows"]).to_pandas().set_index("when"))
