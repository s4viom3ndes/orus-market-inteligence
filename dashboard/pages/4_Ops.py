import json
import datetime
import streamlit as st
import polars as pl
from lib.r2_reader import get_client, R2_BUCKET

st.set_page_config(page_title="Ops - Job Status", page_icon="🛠️", layout="wide")
st.title("🛠️ Ops - Job Status")
st.caption("Ultimo status de cada job + historico das ultimas execucoes")


@st.cache_data(ttl=60)
def list_latest_jobs() -> list[dict]:
    c = get_client()
    r = c.list_objects_v2(Bucket=R2_BUCKET, Prefix="state/job_status/")
    out = []
    for o in r.get("Contents", []):
        if o["Key"].endswith("_latest.json") and "/history/" not in o["Key"]:
            body = c.get_object(Bucket=R2_BUCKET, Key=o["Key"])["Body"].read()
            out.append(json.loads(body))
    return sorted(out, key=lambda x: x.get("finished_at", 0), reverse=True)


@st.cache_data(ttl=60)
def list_history(job_name: str, limit: int = 50) -> list[dict]:
    c = get_client()
    r = c.list_objects_v2(Bucket=R2_BUCKET, Prefix=f"state/job_status/history/{job_name}_")
    contents = sorted(r.get("Contents", []), key=lambda x: x["LastModified"], reverse=True)[:limit]
    out = []
    for o in contents:
        body = c.get_object(Bucket=R2_BUCKET, Key=o["Key"])["Body"].read()
        out.append(json.loads(body))
    return out


latest = list_latest_jobs()

if not latest:
    st.warning("Nenhum job status ainda. Rode um job local ou aguarde o proximo cron.")
    st.stop()

st.subheader("Ultimo status por job")
cards = st.columns(min(len(latest), 4))
for i, j in enumerate(latest):
    with cards[i % len(cards)]:
        status = j.get("status", "?")
        emoji = {"success": "🟢", "failed": "🔴", "running": "🟡"}.get(status, "⚪")
        st.metric(
            f"{emoji} {j['job']}",
            status,
            f"{j.get('duration_sec', 0)}s",
        )
        st.caption(f"finished: {j.get('finished_at_iso', '?')}")
        if j.get("counts"):
            with st.expander("counts"):
                st.json(j["counts"])
        if j.get("error"):
            st.error(j["error"])
            if j.get("traceback"):
                with st.expander("traceback"):
                    st.code(j["traceback"])

st.divider()
st.subheader("Historico de execucoes")

job_name = st.selectbox("Job", [j["job"] for j in latest])
hist = list_history(job_name, limit=50)

if not hist:
    st.info("Sem historico ainda.")
    st.stop()

rows = []
for h in hist:
    r = {
        "started_at": h.get("started_at_iso"),
        "status": h.get("status"),
        "duration_s": h.get("duration_sec"),
    }
    counts = h.get("counts") or {}
    for k in ("rows", "categories_ok", "unique_products", "unique_sellers", "watched_hits",
              "skus_avaliados", "changes", "email_sent", "leaves"):
        if k in counts:
            r[k] = counts[k]
    rows.append(r)

df = pl.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True)

durations = [(h.get("started_at_iso"), h.get("duration_sec")) for h in hist if h.get("duration_sec")]
if len(durations) >= 2:
    st.subheader("Duracao ao longo do tempo")
    chart_df = pl.DataFrame([{"when": d[0], "seconds": d[1]} for d in reversed(durations)])
    st.line_chart(chart_df.to_pandas().set_index("when"))
