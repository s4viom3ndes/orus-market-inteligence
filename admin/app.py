import datetime
import streamlit as st
import polars as pl
from lib.r2 import list_objects, get_json, R2_BUCKET

st.set_page_config(page_title="Orus Admin", page_icon="🛠️", layout="wide")
st.title("🛠️ Orus - Admin")
st.caption(f"Bucket: `{R2_BUCKET}`")

st.subheader("Ultimo status dos jobs")

latest_files = [o for o in list_objects("state/job_status/")
                if o["key"].endswith("_latest.json") and "/history/" not in o["key"]]

if not latest_files:
    st.warning("Nenhum job status ainda. Rode ao menos um job.")
else:
    jobs = sorted(
        [get_json(o["key"]) for o in latest_files],
        key=lambda x: x.get("finished_at", 0),
        reverse=True,
    )

    cols = st.columns(min(len(jobs), 4) or 1)
    for i, j in enumerate(jobs):
        with cols[i % len(cols)]:
            status = j.get("status", "?")
            emoji = {"success": "🟢", "failed": "🔴", "running": "🟡"}.get(status, "⚪")
            st.metric(f"{emoji} {j['job']}", status, f"{j.get('duration_sec', 0)}s")
            st.caption(f"finished: {j.get('finished_at_iso', '?')}")
            counts = j.get("counts")
            if counts:
                with st.expander("counts"):
                    st.json(counts)
            if j.get("error"):
                st.error(j["error"])
                if j.get("traceback"):
                    with st.expander("traceback"):
                        st.code(j["traceback"])

st.divider()

st.subheader("Volume por dataset (R2)")

all_objs = (
    list_objects("market_offers/") +
    list_objects("trends/") +
    list_objects("state/")
)

by_dataset: dict[str, dict] = {}
for o in all_objs:
    top = o["key"].split("/")[0]
    d = by_dataset.setdefault(top, {"n": 0, "total_bytes": 0, "last": None})
    d["n"] += 1
    d["total_bytes"] += o["size"]
    if d["last"] is None or o["last_modified"] > d["last"]:
        d["last"] = o["last_modified"]

df_ds = pl.DataFrame([
    {"dataset": k, "arquivos": v["n"], "size_mb": round(v["total_bytes"] / (1024 * 1024), 2),
     "ultimo": v["last"].strftime("%Y-%m-%d %H:%M UTC") if v["last"] else "-"}
    for k, v in by_dataset.items()
])
st.dataframe(df_ds, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Uso do free tier (Cloudflare R2)")
total_bytes = sum(v["total_bytes"] for v in by_dataset.values())
total_files = sum(v["n"] for v in by_dataset.values())
pct = (total_bytes / (10 * 1024**3)) * 100

c1, c2, c3 = st.columns(3)
c1.metric("Total objetos", f"{total_files}")
c2.metric("Total size", f"{total_bytes/(1024*1024):.2f} MB")
c3.metric("% do free tier 10GB", f"{pct:.4f}%")
st.progress(min(pct / 100, 1.0))

st.divider()
st.caption("Use o menu esquerdo pra ver Snapshots, Historico, Config.")
